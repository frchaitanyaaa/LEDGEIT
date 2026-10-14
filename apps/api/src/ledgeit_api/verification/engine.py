"""Verification engine — 5 independent checks (SPEC §8, CHAITANYA.md §5.7).

Design rule: never trust a stored hash when it can be recomputed. Every check recomputes from the
underlying bytes / canonical JSON / event headers, so an insider who edits rows *and* their stored hashes
is still caught — at the latest by check 5, because the recomputed leaf no longer reaches a root that
exists on-chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from sqlalchemy import Connection, text

from ledgeit_proof import (
    compute_event_hash,
    fmt_ts,
    hash_json,
    leaf_hash,
    sha256_hex,
    verify_chain,
    verify_hex_digest,
)
from ledgeit_proof.merkle import root_from_proof

from ..chain.client import ChainClient
from ..db.json import jdump
from ..services.alerts import raise_alert
from ..services.storage import Storage

PASS, FAIL, PENDING = "PASS", "FAIL", "PENDING"
CLOCK_SKEW = timedelta(minutes=5)
REQUIRED_EVENTS = ("INSPECTED", "EVIDENCE_HASHED", "RECORD_CREATED")


@dataclass
class Check:
    name: str
    title: str
    status: str = PASS
    problems: list[str] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)

    def fail(self, msg: str) -> None:
        self.status = FAIL
        self.problems.append(msg)

    def pending(self, msg: str) -> None:
        if self.status == PASS:
            self.status = PENDING
        self.problems.append(msg)

    def out(self) -> dict:
        return {"status": self.status, "title": self.title, "problems": self.problems, "facts": self.facts}


def _load(conn: Connection, inspection_id: str) -> dict:
    row = conn.execute(text("""
        SELECT i.*, i.id::text AS sid, l.code AS line_code, d.device_code, d.public_key AS device_public_key,
               b.batch_code, ev.sha256 AS ev_sha, ev.storage_uri AS ev_uri, hm.sha256 AS hm_sha, hm.storage_uri AS hm_uri,
               m.name AS m_name, m.version AS m_version, m.weights_sha256 AS m_weights, m.status::text AS m_status,
               m.approved_at AS m_approved_at, m.retired_at AS m_retired_at
        FROM inspections i JOIN production_lines l ON l.id=i.line_id JOIN devices d ON d.id=i.device_id
        JOIN batches b ON b.id=i.batch_id JOIN evidence ev ON ev.id=i.evidence_id
        LEFT JOIN evidence hm ON hm.id=i.heatmap_evidence_id JOIN ai_models m ON m.id=i.model_id
        WHERE i.id=:i
    """), {"i": inspection_id}).mappings().one()
    return dict(row)


def _events(conn: Connection, where: str, params: dict) -> list[dict]:
    rows = conn.execute(text(
        "SELECT id, seq, event_type::text AS event_type, actor_type::text AS actor_type, actor_id, payload, "
        "payload_hash, prev_event_hash, event_hash, signature, created_at, inspection_id::text AS inspection_id "
        "FROM inspection_events WHERE " + where + " ORDER BY seq"), params).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        d["created_at"] = fmt_ts(d["created_at"])
        out.append(d)
    return out


def _recomputed_event_hash(line: str, e: dict) -> str:
    return compute_event_hash(line=line, seq=e["seq"], event_type=e["event_type"], actor_type=e["actor_type"],
                              actor_id=e["actor_id"], payload_hash=hash_json(e["payload"]),
                              prev_event_hash=e["prev_event_hash"], created_at=e["created_at"])


# ---------------------------------------------------------------- checks

def check_evidence(ins: dict, rec: dict, storage: Storage) -> Check:
    c = Check("evidence", "Evidence hash")
    expected = {"image": (rec["evidence"]["sha256"], ins["ev_uri"])}
    hm = rec["explanation"].get("heatmap_sha256")
    if hm:
        expected["heatmap"] = (hm, ins["hm_uri"])
    for kind, (want, uri) in expected.items():
        if not uri:
            c.fail(f"{kind}: evidence object missing")
            continue
        try:
            got = sha256_hex(storage.get(uri))
        except Exception as e:
            c.fail(f"{kind}: cannot read stored object ({type(e).__name__})")
            continue
        c.facts[f"{kind}_sha256"] = got
        if got != want:
            c.fail(f"{kind}: stored bytes hash to {got[:16]}…, record says {want[:16]}…")
    if ins["ev_sha"] != rec["evidence"]["sha256"]:
        c.fail("evidence table sha256 differs from the sealed record")
    return c


def check_model(ins: dict, rec: dict) -> Check:
    c = Check("model", "Model hash + approval")
    m = rec["model"]
    c.facts.update({"model": f"{m['name']}@{m['version']}", "weights_sha256": m["weights_sha256"]})
    if (ins["m_name"], ins["m_version"]) != (m["name"], m["version"]):
        c.fail("inspection points to a different model than the sealed record")
    if ins["m_weights"] != m["weights_sha256"]:
        c.fail("registry weights_sha256 differs from the sealed record")
    t = ins["inspected_at"]
    approved = ins["m_status"] in ("APPROVED", "RETIRED") and ins["m_approved_at"] is not None \
        and ins["m_approved_at"] <= t and (ins["m_retired_at"] is None or ins["m_retired_at"] > t)
    if not approved:
        c.fail(f"model was not APPROVED at inspected_at (status {ins['m_status']})")
    return c


def check_signatures(conn: Connection, ins: dict, rec: dict, events: list[dict]) -> Check:
    c = Check("signature", "Device + human signatures")
    record_hash = hash_json(rec)
    if verify_hex_digest(record_hash, ins["device_signature"], ins["device_public_key"]):
        c.facts["device"] = f"{ins['device_code']}: valid"
    else:
        c.fail(f"device signature by {ins['device_code']} does not verify over the recomputed record hash")
    humans = 0
    for e in events:
        if e["actor_type"] != "USER":
            continue
        humans += 1
        p = e["payload"].get("payload") if isinstance(e["payload"], dict) else None
        sig = e["payload"].get("signature") if isinstance(e["payload"], dict) else None
        if not p or not sig:
            c.fail(f"seq {e['seq']} {e['event_type']}: missing signed payload")
            continue
        signer = p.get("operator") or p.get("reviewer") or p.get("approver") or p.get("actor") or {}
        if signer.get("employee_code") != e["actor_id"]:
            c.fail(f"seq {e['seq']}: signer {signer.get('employee_code')} is not the event actor {e['actor_id']}")
        registered = conn.execute(text(
            "SELECT 1 FROM user_keys k JOIN users u ON u.id=k.user_id WHERE u.employee_code=:c AND k.public_key=:pk"
        ), {"c": e["actor_id"], "pk": signer.get("public_key")}).first()
        if not registered:
            c.fail(f"seq {e['seq']}: key is not registered to {e['actor_id']}")
        try:
            digest = hash_json(p)
        except ValueError:
            c.fail(f"seq {e['seq']}: payload not canonicalizable")
            continue
        if digest != e["payload"].get("payload_hash"):
            c.fail(f"seq {e['seq']}: signed payload does not hash to its payload_hash")
        if not verify_hex_digest(digest, sig, signer.get("public_key", "")):
            c.fail(f"seq {e['seq']} {e['event_type']}: signature by {e['actor_id']} is invalid")
        if p.get("inspection_id") != ins["sid"] or (p.get("record_hash") not in (None, record_hash)):
            c.fail(f"seq {e['seq']}: signed payload refers to a different inspection/record")
    c.facts["human_signatures"] = humans
    return c


def check_chain(conn: Connection, ins: dict, rec: dict, events: list[dict]) -> Check:
    c = Check("chain", "Event chain")
    line = ins["line_code"]
    record_hash = hash_json(rec)
    c.facts["recomputed_record_hash"] = record_hash
    # (a) stored record row vs sealed canonical record
    r = rec["result"]
    pairs = {
        "record_hash": (ins["record_hash"], record_hash),
        "decision": (ins["decision"], r["decision"]),
        "defect_class": (ins["defect_class"], r.get("defect_class")),
        "severity": (ins["severity"], r["severity"]),
        "confidence": (f"{ins['confidence']:.4f}", r["confidence"]),
        "unit_serial": (ins["unit_serial"], rec["unit_serial"]),
        "inspection_code": (ins["inspection_code"], rec["inspection_code"]),
        "inspected_at": (fmt_ts(ins["inspected_at"]), rec["inspected_at"]),
        "line": (line, rec["line"]),
        "device": (ins["device_code"], rec["device"]),
        "batch": (ins["batch_code"], rec["batch_code"]),
    }
    for k, (stored, sealed) in pairs.items():
        if stored != sealed:
            c.fail(f"{k}: database says {stored!r} but the sealed record says {sealed!r}")
    # (b) device events bind the record
    by_type: dict[str, list[dict]] = {}
    for e in events:
        by_type.setdefault(e["event_type"], []).append(e)
    for t in REQUIRED_EVENTS:
        if len(by_type.get(t, [])) != 1:
            c.fail(f"required event {t} missing or duplicated")
    if by_type.get("RECORD_CREATED") and by_type["RECORD_CREATED"][0]["payload"].get("record_hash") != record_hash:
        c.fail("RECORD_CREATED event does not commit to the recomputed record hash")
    if by_type.get("INSPECTED") and by_type["INSPECTED"][0]["payload"].get("decision") != r["decision"]:
        c.fail("INSPECTED event decision differs from the sealed record")
    if by_type.get("EVIDENCE_HASHED") and \
            by_type["EVIDENCE_HASHED"][0]["payload"].get("evidence_sha256") != rec["evidence"]["sha256"]:
        c.fail("EVIDENCE_HASHED event differs from the sealed record")
    # (c) overrides table must match chained OVERRIDDEN payloads
    chained = {e["payload"].get("payload_hash") for e in by_type.get("OVERRIDDEN", [])}
    for (ph,) in conn.execute(text("SELECT payload_hash FROM overrides WHERE inspection_id=:i"), {"i": ins["sid"]}):
        if ph not in chained:
            c.fail("an override row has no matching OVERRIDDEN event in the chain")
    # (d) the line segment around this inspection links and has no gaps
    if events:
        lo, hi = events[0]["seq"], events[-1]["seq"]
        seg = _events(conn, "line_id=:l AND seq BETWEEN :a AND :b", {"l": ins["line_id"], "a": max(1, lo - 1),
                                                                      "b": hi + 1})
        issues = verify_chain(line, seg, expected_first_seq=max(1, lo - 1))
        for i in issues:
            c.fail(f"seq {i.seq}: {i.code} — {i.detail}")
        c.facts["segment"] = f"{line} seq {seg[0]['seq'] if seg else '?'}..{seg[-1]['seq'] if seg else '?'}"
        head = conn.execute(text("SELECT last_seq, last_event_hash FROM line_heads WHERE line_id=:l"),
                            {"l": ins["line_id"]}).one()
        last = conn.execute(text("SELECT seq, event_hash FROM inspection_events WHERE line_id=:l ORDER BY seq DESC "
                                 "LIMIT 1"), {"l": ins["line_id"]}).one()
        if (last.seq, last.event_hash) != (head.last_seq, head.last_event_hash):
            c.fail(f"line head says seq {head.last_seq} but the newest stored event is seq {last.seq} "
                   "(events deleted from the end of the chain)")
    c.facts["events"] = len(events)
    return c


def check_anchor(conn: Connection, ins: dict, events: list[dict], chain: ChainClient | None) -> Check:
    c = Check("anchor", "Merkle proof to on-chain root")
    line = ins["line_code"]
    roots: dict[str, Any] = {}
    anchored = 0
    for e in events:
        item = conn.execute(text(
            "SELECT ai.merkle_proof, ai.batch_id, b.merkle_root, b.status::text AS status, b.leaf_count "
            "FROM anchor_items ai JOIN anchor_batches b ON b.id=ai.batch_id WHERE ai.event_id=:e"
        ), {"e": e["id"]}).mappings().first()
        if not item:
            queued = conn.execute(text("SELECT 1 FROM anchor_queue WHERE event_id=:e"), {"e": e["id"]}).first()
            if queued:
                c.pending(f"seq {e['seq']} {e['event_type']}: waiting in the anchoring window")
            else:
                c.fail(f"seq {e['seq']} {e['event_type']}: not anchored and not queued")
            continue
        leaf = leaf_hash(_recomputed_event_hash(line, e))
        try:
            root = root_from_proof(leaf, item["merkle_proof"])
        except (ValueError, KeyError, TypeError):
            c.fail(f"seq {e['seq']}: malformed Merkle proof")
            continue
        if root != item["merkle_root"]:
            c.fail(f"seq {e['seq']}: recomputed leaf does not reach the recorded batch root")
        if chain is None:
            c.pending("no blockchain configured (CHAIN=none)")
            continue
        if root not in roots:
            try:
                roots[root] = chain.get_anchor(root)
            except Exception as ex:
                c.pending(f"chain unreachable: {type(ex).__name__}")
                roots[root] = "ERR"
        onchain = roots[root]
        if onchain == "ERR":
            continue
        if onchain is None:
            if item["status"] == "CONFIRMED" and root == item["merkle_root"]:
                c.fail(f"seq {e['seq']}: batch {item['batch_id']} root is not on-chain")
            elif root != item["merkle_root"]:
                c.fail(f"seq {e['seq']}: recomputed root {root[:16]}… does not exist on-chain")
            else:
                c.pending(f"seq {e['seq']}: batch {item['batch_id']} {item['status']} (not yet on-chain)")
            continue
        if onchain.timestamp < ins["inspected_at"] - CLOCK_SKEW:
            c.fail(f"seq {e['seq']}: on-chain anchor predates the inspection")
        anchored += 1
    c.facts.update({"anchored_events": anchored, "events": len(events),
                    "roots": sorted(r for r in roots if roots[r] not in (None, "ERR"))})
    if chain is not None:
        c.facts.update({"network": chain.network, "chain_id": chain.chain_id, "contract": chain.contract_address})
    return c


# ---------------------------------------------------------------- orchestration

def verify_inspection(conn: Connection, inspection_id: str, *, storage: Storage, chain: ChainClient | None,
                      requested_by: str | None = None, persist: bool = True) -> dict:
    ins = _load(conn, inspection_id)
    rec = ins["canonical_record"]
    events = _events(conn, "inspection_id=:i", {"i": inspection_id})
    checks = [
        check_evidence(ins, rec, storage),
        check_model(ins, rec),
        check_signatures(conn, ins, rec, events),
        check_chain(conn, ins, rec, events),
        check_anchor(conn, ins, events, chain),
    ]
    statuses = [c.status for c in checks]
    if FAIL in statuses:
        result = "FAILED"
    elif PENDING in statuses:
        result = "PENDING_ANCHOR"
    else:
        result = "VERIFIED"
    out = {"inspection_id": inspection_id, "inspection_code": ins["inspection_code"], "result": result,
           "message": {"VERIFIED": "Record has not changed since it was sealed",
                       "FAILED": "Verification Failed — Record mismatch detected",
                       "PENDING_ANCHOR": "Integrity checks pass; waiting for the on-chain anchor"}[result],
           "checks": {c.name: c.out() for c in checks}}
    if persist:
        vid = conn.execute(text(
            "INSERT INTO verifications(inspection_id, requested_by, result, checks) "
            "VALUES (:i, :u, CAST(:r AS verify_result_t), CAST(:c AS jsonb)) RETURNING id::text, verified_at"
        ), {"i": inspection_id, "u": requested_by, "r": result, "c": jdump(out["checks"])}).one()
        out["verification_id"], out["verified_at"] = vid[0], fmt_ts(vid[1])
        conn.execute(text("UPDATE inspection_status SET last_verification=CAST(:r AS verify_result_t), "
                          "updated_at=now() WHERE inspection_id=:i"), {"r": result, "i": inspection_id})
        if result == "FAILED":
            failed = [c.name for c in checks if c.status == FAIL]
            raise_alert(conn, "TAMPER_DETECTED", "HIGH",
                        {"failed_checks": failed, "problems": [p for c in checks for p in c.problems][:10]},
                        inspection_id, dedupe=True)
    return out
