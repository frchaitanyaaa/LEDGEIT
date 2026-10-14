"""Anchor worker (CHAITANYA.md §6.2, ADR-008).

tick():
  1. flush   — per risk level, cut a Merkle batch from anchor_queue when the window is full or old enough
  2. submit  — send each PENDING batch root to LedgeitAnchor; retry with exponential backoff; FAILED after N
  3. project — mark inspections whose events are all in CONFIRMED batches as anchor_status=CONFIRMED

No ANCHORED event is appended to the hash chain: that event would itself need anchoring (infinite
regress). Anchor state lives in anchor_batches / blockchain_txs / inspection_status instead.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import Connection, Engine, text

from ledgeit_proof import build_tree

from ..chain.client import AlreadyAnchored, ChainClient, TxResult
from ..core.yamlconf import economics_config, risk_config
from ..db.json import jdump
from ..services.alerts import raise_alert
from ..services.feed import hub

log = logging.getLogger("ledgeit.anchor")
RISK_INT = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def flush(conn: Connection, now: datetime, force: bool = False) -> list[int]:
    """Cut batches from the queue. Returns new batch ids."""
    cfg = risk_config()["anchoring"]
    created: list[int] = []
    for risk in ("HIGH", "MEDIUM", "LOW"):
        rule = cfg[risk]
        max_items, max_wait = int(rule["max_items"]), int(rule["max_wait_seconds"])
        while True:
            rows = conn.execute(text(
                "SELECT q.event_id, q.enqueued_at, e.event_hash FROM anchor_queue q "
                "JOIN inspection_events e ON e.id=q.event_id WHERE q.batch_id IS NULL AND q.risk_level=CAST(:r AS risk_t) "
                "ORDER BY q.event_id LIMIT :n FOR UPDATE OF q SKIP LOCKED"
            ), {"r": risk, "n": max_items}).mappings().all()
            if not rows:
                break
            oldest = min(r["enqueued_at"] for r in rows)
            full = len(rows) >= max_items
            due = (now - oldest) >= timedelta(seconds=max_wait)
            if not (full or due or force):
                break
            tree = build_tree([r["event_hash"] for r in rows])
            bid = conn.execute(text(
                "INSERT INTO anchor_batches(merkle_root, leaf_count, risk_level) VALUES (:root, :n, CAST(:r AS risk_t)) "
                "RETURNING id"
            ), {"root": tree.root, "n": len(rows), "r": risk}).scalar_one()
            for i, r in enumerate(rows):
                conn.execute(text(
                    "INSERT INTO anchor_items(batch_id, event_id, leaf_index, leaf_hash, merkle_proof) "
                    "VALUES (:b, :e, :i, :l, CAST(:p AS jsonb))"
                ), {"b": bid, "e": r["event_id"], "i": i, "l": tree.leaves[i], "p": jdump(tree.proofs[i])})
            conn.execute(text("UPDATE anchor_queue SET batch_id=:b WHERE event_id = ANY(:ids)"),
                         {"b": bid, "ids": [r["event_id"] for r in rows]})
            created.append(bid)
            log.info("batch %s: %s %s leaves root=%s", bid, risk, len(rows), tree.root[:16])
            if not full:
                break
    return created


def _record_tx(conn: Connection, chain: ChainClient, batch_id: int, tx: TxResult) -> None:
    econ = economics_config()
    rate = Decimal(econ["native_to_inr"] if chain.chain_id == 80002 else econ.get("eth_local_to_inr", "0"))
    fee = tx.fee_native
    conn.execute(text(
        "INSERT INTO blockchain_txs(batch_id, network, chain_id, contract_address, tx_hash, block_number, "
        "block_timestamp, gas_used, effective_gas_price_wei, fee_native, fee_inr) VALUES (:b, :n, :c, :a, :h, :bn, "
        ":bt, :g, :p, :f, :fi) ON CONFLICT (tx_hash) DO NOTHING"
    ), {"b": batch_id, "n": chain.network, "c": chain.chain_id, "a": chain.contract_address, "h": tx.tx_hash,
        "bn": tx.block_number, "bt": tx.block_timestamp, "g": tx.gas_used, "p": tx.effective_gas_price_wei,
        "f": fee, "fi": (fee * rate).quantize(Decimal("0.0001"))})
    conn.execute(text(
        "UPDATE anchor_batches SET status='CONFIRMED', confirmed_at=:t, submitted_tx_hash=:h, last_error=NULL "
        "WHERE id=:b"
    ), {"t": tx.block_timestamp, "h": tx.tx_hash, "b": batch_id})


def submit(engine: Engine, chain: ChainClient, now: datetime) -> list[int]:
    """Submit pending batches one by one (each in its own transaction). Returns confirmed batch ids."""
    max_attempts = int(risk_config()["anchoring"].get("max_attempts", 5))
    with engine.begin() as conn:
        pending = conn.execute(text(
            "SELECT id, merkle_root, leaf_count, risk_level::text AS risk, attempts, last_attempt_at FROM anchor_batches "
            "WHERE status IN ('PENDING','SUBMITTED') ORDER BY CASE risk_level WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1 "
            "ELSE 2 END, id"
        )).mappings().all()
    confirmed: list[int] = []
    for b in pending:
        if b["attempts"] and b["last_attempt_at"]:
            backoff = timedelta(seconds=min(2 ** b["attempts"], 60))
            if now - b["last_attempt_at"] < backoff:
                continue
        with engine.begin() as conn:
            locked = conn.execute(text(
                "SELECT id FROM anchor_batches WHERE id=:b AND status IN ('PENDING','SUBMITTED') FOR UPDATE SKIP LOCKED"
            ), {"b": b["id"]}).first()
            if not locked:
                continue
            try:
                try:
                    tx = chain.anchor(b["merkle_root"], b["id"], b["leaf_count"], RISK_INT[b["risk"]])
                except AlreadyAnchored:
                    tx = chain.find_anchor_tx(b["merkle_root"])
                    if tx is None:
                        raise
                _record_tx(conn, chain, b["id"], tx)
                confirmed.append(b["id"])
                log.info("batch %s confirmed in block %s tx %s", b["id"], tx.block_number, tx.tx_hash)
            except Exception as e:  # RPC down, revert, timeout...
                attempts = b["attempts"] + 1
                status = "FAILED" if attempts >= max_attempts else "PENDING"
                conn.execute(text(
                    "UPDATE anchor_batches SET attempts=:a, last_attempt_at=:t, last_error=:e, "
                    "status=CAST(:s AS anchor_status_t) WHERE id=:b"
                ), {"a": attempts, "t": now, "e": str(e)[:500], "s": status, "b": b["id"]})
                log.warning("batch %s attempt %s failed: %s", b["id"], attempts, e)
                if status == "FAILED":
                    raise_alert(conn, "MISSING_ANCHOR", "HIGH", {"batch_id": b["id"], "merkle_root": b["merkle_root"],
                                                                 "attempts": attempts, "error": str(e)[:300]})
    return confirmed


def project(conn: Connection, batch_ids: list[int]) -> list[str]:
    """Update inspection_status.anchor_status for inspections touched by these batches."""
    if not batch_ids:
        return []
    rows = conn.execute(text("""
        WITH touched AS (
          SELECT DISTINCT e.inspection_id FROM anchor_items ai JOIN inspection_events e ON e.id = ai.event_id
          WHERE ai.batch_id = ANY(:b)
        )
        UPDATE inspection_status s SET anchor_status = CASE
            WHEN NOT EXISTS (
              SELECT 1 FROM inspection_events e
              LEFT JOIN anchor_items ai ON ai.event_id = e.id
              LEFT JOIN anchor_batches ab ON ab.id = ai.batch_id
              WHERE e.inspection_id = s.inspection_id AND (ab.status IS DISTINCT FROM 'CONFIRMED')
            ) THEN 'CONFIRMED'::anchor_status_t ELSE s.anchor_status END,
          updated_at = now()
        FROM touched t WHERE s.inspection_id = t.inspection_id
        RETURNING s.inspection_id::text, s.anchor_status::text
    """), {"b": batch_ids}).all()
    return [r[0] for r in rows if r[1] == "CONFIRMED"]


def tick(engine: Engine, chain: ChainClient | None, now: datetime | None = None, force: bool = False) -> dict:
    now = now or datetime.now(timezone.utc)
    with engine.begin() as conn:
        created = flush(conn, now, force=force)
    confirmed = submit(engine, chain, now) if chain else []
    with engine.begin() as conn:
        done = project(conn, confirmed)
    if created or confirmed:
        hub.publish("anchor", {"created_batches": created, "confirmed_batches": confirmed, "inspections": done})
    return {"created": created, "confirmed": confirmed, "inspections_confirmed": done}
