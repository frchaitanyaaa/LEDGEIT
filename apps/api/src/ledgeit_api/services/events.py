"""The ONLY writer of inspection_events: appends to a line's hash chain and enqueues for anchoring."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, text

from ledgeit_proof import compute_event_hash, fmt_ts, hash_json

from ..core.time import now_ms
from ..db.json import jdump


def append_event(
    conn: Connection,
    *,
    inspection_id: str,
    line_id: str,
    line_code: str,
    event_type: str,
    actor_type: str,
    actor_id: str | None,
    payload: dict[str, Any],
    risk: str,
    signature: str | None = None,
) -> dict[str, Any]:
    head = conn.execute(
        text("SELECT last_seq, last_event_hash FROM line_heads WHERE line_id=:l FOR UPDATE"), {"l": line_id}
    ).one()
    seq = int(head.last_seq) + 1
    prev = head.last_event_hash
    created = now_ms()
    created_s = fmt_ts(created)
    payload_hash = hash_json(payload)
    event_hash = compute_event_hash(
        line=line_code, seq=seq, event_type=event_type, actor_type=actor_type, actor_id=actor_id,
        payload_hash=payload_hash, prev_event_hash=prev, created_at=created_s,
    )
    eid = conn.execute(text(
        "INSERT INTO inspection_events(inspection_id, line_id, seq, event_type, actor_type, actor_id, payload, "
        "payload_hash, prev_event_hash, event_hash, signature, created_at) VALUES (:i, :l, :s, CAST(:et AS event_t), "
        "CAST(:at AS actor_t), :aid, CAST(:p AS jsonb), :ph, :prev, :eh, :sig, :c) RETURNING id"
    ), {"i": inspection_id, "l": line_id, "s": seq, "et": event_type, "at": actor_type, "aid": actor_id,
        "p": jdump(payload), "ph": payload_hash, "prev": prev, "eh": event_hash, "sig": signature,
        "c": created}).scalar_one()
    conn.execute(text("UPDATE line_heads SET last_seq=:s, last_event_hash=:h, updated_at=now() WHERE line_id=:l"),
                 {"s": seq, "h": event_hash, "l": line_id})
    conn.execute(text("INSERT INTO anchor_queue(event_id, risk_level) VALUES (:e, CAST(:r AS risk_t))"),
                 {"e": eid, "r": risk})
    conn.execute(text(
        "UPDATE inspection_status SET last_event_id=:e, anchor_status='PENDING', updated_at=now() WHERE inspection_id=:i"
    ), {"e": eid, "i": inspection_id})
    return {"id": eid, "seq": seq, "event_type": event_type, "event_hash": event_hash, "prev_event_hash": prev,
            "payload_hash": payload_hash, "created_at": created_s}


def set_status(conn: Connection, inspection_id: str, status: str, final_decision: str | None = None) -> None:
    conn.execute(text(
        "UPDATE inspection_status SET status=:s, final_decision=COALESCE(CAST(:d AS decision_t), final_decision), "
        "updated_at=now() WHERE inspection_id=:i"
    ), {"s": status, "d": final_decision, "i": inspection_id})
