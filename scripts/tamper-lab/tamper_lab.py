"""LEDGEIT Tamper Lab — simulates a malicious DBA / insider (CHAITANYA.md §6.6).

Connects with TAMPER_DATABASE_URL (a Postgres superuser) and sets session_replication_role=replica,
which silently disables the append-only triggers — exactly what a real DBA could do. Then run
verification and watch it fail.

  python scripts/tamper-lab/tamper_lab.py edit-decision  INS-...   # flip FAIL->PASS in the DB      -> checks 3+4 FAIL
  python scripts/tamper-lab/tamper_lab.py swap-image     INS-...   # replace the stored image       -> check 1 FAIL
  python scripts/tamper-lab/tamper_lab.py delete-event   INS-...   # delete the newest event        -> check 4 FAIL (seq gap / head)
  python scripts/tamper-lab/tamper_lab.py smart-insider  INS-...   # edit + re-sign + recompute ALL hashes, proofs and roots
                                                                   #                                -> only check 5 FAILS
  python -m simulator --replay N                                   # replay attack -> DUPLICATE_EVIDENCE alert
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from pathlib import Path

from sqlalchemy import Connection, create_engine, text

ROOT = Path(__file__).resolve().parents[2]

from ledgeit_proof import (  # noqa: E402
    build_tree,
    compute_event_hash,
    fmt_ts,
    hash_json,
    sign_hex_digest,
)


def _engine(url: str | None = None):
    from ledgeit_api.core.config import get_settings

    s = get_settings()
    return create_engine(url or os.environ.get("TAMPER_DATABASE_URL") or s.tamper_database_url or s.database_url)


def _as_dba(conn: Connection) -> None:
    conn.execute(text("SET LOCAL session_replication_role = replica"))  # triggers OFF (superuser only)


def _inspection(conn: Connection, code: str) -> dict:
    row = conn.execute(text(
        "SELECT i.id::text AS id, i.inspection_code, i.decision::text AS decision, i.canonical_record, i.line_id::text "
        "AS line_id, l.code AS line, d.device_code, ev.storage_uri FROM inspections i JOIN production_lines l "
        "ON l.id=i.line_id JOIN devices d ON d.id=i.device_id JOIN evidence ev ON ev.id=i.evidence_id "
        "WHERE i.inspection_code=:c OR i.id::text=:c"), {"c": code}).mappings().first()
    if not row:
        raise SystemExit(f"inspection {code} not found")
    return dict(row)


def edit_decision(engine, code: str, new: str | None = None) -> dict:
    """The naive cover-up: change the decision in the DB row and in the stored JSON."""
    with engine.begin() as conn:
        _as_dba(conn)
        ins = _inspection(conn, code)
        new = new or ("PASS" if ins["decision"] == "FAIL" else "FAIL")
        conn.execute(text(
            "UPDATE inspections SET decision=CAST(:d AS decision_t), "
            "canonical_record=jsonb_set(canonical_record, '{result,decision}', to_jsonb(CAST(:d AS text))) WHERE id=:i"
        ), {"d": new, "i": ins["id"]})
        conn.execute(text("UPDATE inspection_status SET status=:s, final_decision=CAST(:d AS decision_t) "
                          "WHERE inspection_id=:i"), {"s": "RELEASED" if new == "PASS" else "REJECTED", "d": new,
                                                      "i": ins["id"]})
    return {"attack": "edit-decision", "inspection": ins["inspection_code"], "from": ins["decision"], "to": new}


def swap_image(engine, code: str, replacement: bytes | None = None) -> dict:
    """Replace the evidence object in storage with a clean-looking image."""
    from ledgeit_api.services.storage import get_storage

    with engine.begin() as conn:
        ins = _inspection(conn, code)
    if replacement is None:
        import numpy as np
        from PIL import Image

        rng = np.random.default_rng(1)
        img = (np.full((200, 200), 128) + rng.normal(0, 3, (200, 200))).clip(0, 255).astype("uint8")
        buf = io.BytesIO()
        Image.fromarray(img).save(buf, format="JPEG", quality=92)
        replacement = buf.getvalue()
    get_storage().overwrite(ins["storage_uri"], replacement)
    return {"attack": "swap-image", "inspection": ins["inspection_code"], "object": ins["storage_uri"]}


def delete_event(engine, code: str, event_type: str | None = None) -> dict:
    """Delete an event (default: the inspection's newest one, e.g. REJECTED)."""
    with engine.begin() as conn:
        _as_dba(conn)
        ins = _inspection(conn, code)
        q = "SELECT id, seq, event_type::text FROM inspection_events WHERE inspection_id=:i"
        p = {"i": ins["id"]}
        if event_type:
            q += " AND event_type=CAST(:t AS event_t)"
            p["t"] = event_type
        ev = conn.execute(text(q + " ORDER BY seq DESC LIMIT 1"), p).first()
        if not ev:
            raise SystemExit("no matching event")
        for t in ("anchor_queue", "anchor_items"):
            conn.execute(text(f"DELETE FROM {t} WHERE event_id=:e"), {"e": ev[0]})
        conn.execute(text("DELETE FROM override_approvals WHERE event_id=:e"), {"e": ev[0]})
        conn.execute(text("DELETE FROM overrides WHERE event_id=:e"), {"e": ev[0]})
        conn.execute(text("UPDATE inspection_status SET last_event_id=NULL WHERE last_event_id=:e"), {"e": ev[0]})
        conn.execute(text("DELETE FROM inspection_events WHERE id=:e"), {"e": ev[0]})
    return {"attack": "delete-event", "inspection": ins["inspection_code"], "deleted": {"seq": ev[1], "type": ev[2]}}


def smart_insider(engine, code: str, device_seed_b64: str | None = None, new: str | None = None) -> dict:
    """Edit the record, re-sign it with a compromised device key, and recompute EVERY dependent hash:
    record hash, event payload hashes, the whole line chain suffix, line head, Merkle leaves, proofs and
    batch roots. The database becomes perfectly self-consistent; only the on-chain roots disagree."""
    with engine.begin() as conn:
        _as_dba(conn)
        ins = _inspection(conn, code)
        if device_seed_b64 is None:
            key = ROOT / "services" / "edge-simulator" / "keys" / f"{ins['device_code']}.json"
            device_seed_b64 = json.loads(key.read_text())["seed_b64"]
        rec = ins["canonical_record"]
        new = new or ("PASS" if rec["result"]["decision"] == "FAIL" else "FAIL")
        rec["result"].update({"decision": new, "defect_class": None if new == "PASS" else "scratches",
                              "severity": "NONE" if new == "PASS" else "MAJOR", "boxes": []})
        rh = hash_json(rec)
        sig = sign_hex_digest(rh, device_seed_b64)
        conn.execute(text(
            "UPDATE inspections SET decision=CAST(:d AS decision_t), defect_class=:c, severity=CAST(:s AS severity_t), "
            "canonical_record=CAST(:r AS jsonb), record_hash=:h, device_signature=:sig WHERE id=:i"
        ), {"d": new, "c": rec["result"]["defect_class"], "s": rec["result"]["severity"], "r": json.dumps(rec),
            "h": rh, "sig": sig, "i": ins["id"]})
        # rewrite this inspection's device event payloads
        for et, patch in (("INSPECTED", {"decision": new}), ("RECORD_CREATED", {"record_hash": rh, "device_signature": sig})):
            row = conn.execute(text("SELECT id, payload FROM inspection_events WHERE inspection_id=:i AND "
                                    "event_type=CAST(:t AS event_t)"), {"i": ins["id"], "t": et}).first()
            payload = {**row[1], **patch}
            conn.execute(text("UPDATE inspection_events SET payload=CAST(:p AS jsonb), payload_hash=:ph, signature="
                              "CASE WHEN event_type='RECORD_CREATED' THEN :sig ELSE signature END WHERE id=:e"),
                         {"p": json.dumps(payload), "ph": hash_json(payload), "sig": sig, "e": row[0]})
        # recompute the chain suffix of the whole line
        first = conn.execute(text("SELECT min(seq) FROM inspection_events WHERE inspection_id=:i"),
                             {"i": ins["id"]}).scalar()
        prev = conn.execute(text("SELECT event_hash FROM inspection_events WHERE line_id=:l AND seq=:s"),
                            {"l": ins["line_id"], "s": first - 1}).scalar()
        if prev is None:
            prev = conn.execute(text("SELECT genesis_hash FROM production_lines WHERE id=:l"),
                                {"l": ins["line_id"]}).scalar()
        rows = conn.execute(text(
            "SELECT id, seq, event_type::text, actor_type::text, actor_id, payload_hash, created_at FROM "
            "inspection_events WHERE line_id=:l AND seq>=:s ORDER BY seq"), {"l": ins["line_id"], "s": first}).all()
        rewritten = []
        for r in rows:
            eh = compute_event_hash(line=ins["line"], seq=r[1], event_type=r[2], actor_type=r[3], actor_id=r[4],
                                    payload_hash=r[5], prev_event_hash=prev, created_at=fmt_ts(r[6]))
            conn.execute(text("UPDATE inspection_events SET prev_event_hash=:p, event_hash=:h WHERE id=:e"),
                         {"p": prev, "h": eh, "e": r[0]})
            rewritten.append(r[0])
            prev = eh
        conn.execute(text("UPDATE line_heads SET last_event_hash=:h WHERE line_id=:l"), {"h": prev, "l": ins["line_id"]})
        # rebuild every affected Merkle batch so proofs and roots match the new hashes
        batches = [b for (b,) in conn.execute(text(
            "SELECT DISTINCT batch_id FROM anchor_items WHERE event_id = ANY(:e)"), {"e": rewritten})]
        for b in batches:
            items = conn.execute(text(
                "SELECT ai.id, e.event_hash FROM anchor_items ai JOIN inspection_events e ON e.id=ai.event_id "
                "WHERE ai.batch_id=:b ORDER BY ai.leaf_index"), {"b": b}).all()
            tree = build_tree([h for _, h in items])
            for (aid, _), leaf, proof in zip(items, tree.leaves, tree.proofs):
                conn.execute(text("UPDATE anchor_items SET leaf_hash=:l, merkle_proof=CAST(:p AS jsonb) WHERE id=:i"),
                             {"l": leaf, "p": json.dumps(proof), "i": aid})
            conn.execute(text("UPDATE anchor_batches SET merkle_root=:r WHERE id=:b"), {"r": tree.root, "b": b})
        conn.execute(text("UPDATE inspection_status SET status=:s, final_decision=CAST(:d AS decision_t) "
                          "WHERE inspection_id=:i"), {"s": "RELEASED" if new == "PASS" else "REJECTED", "d": new,
                                                      "i": ins["id"]})
    return {"attack": "smart-insider", "inspection": ins["inspection_code"], "to": new, "new_record_hash": rh,
            "events_rewritten": len(rewritten), "batches_rebuilt": len(batches)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("attack", choices=["edit-decision", "swap-image", "delete-event", "smart-insider"])
    ap.add_argument("inspection", help="inspection code or id")
    ap.add_argument("--to", choices=["PASS", "FAIL"], help="new decision (default: flip)")
    ap.add_argument("--event-type", help="delete-event: which event type (default newest)")
    ap.add_argument("--db", help="superuser DB URL (default TAMPER_DATABASE_URL)")
    a = ap.parse_args(argv)
    eng = _engine(a.db)
    if a.attack == "edit-decision":
        out = edit_decision(eng, a.inspection, a.to)
    elif a.attack == "swap-image":
        out = swap_image(eng, a.inspection)
    elif a.attack == "delete-event":
        out = delete_event(eng, a.inspection, a.event_type)
    else:
        out = smart_insider(eng, a.inspection, new=a.to)
    print(json.dumps(out, indent=2))
    print(f"\nNow verify:  POST /api/v1/inspections/{out['inspection']}/verify   (or the Verification Center page)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
