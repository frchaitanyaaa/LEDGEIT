"""Blockchain Explorer + alerts endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import Connection, text

from ..auth.deps import ALL_ROLES, CurrentUser, require_roles
from ..chain.client import EXPLORERS, get_chain
from ..core.config import get_settings
from ..core.errors import ApiError, not_found
from ..core.time import iso, now_ms
from ..db.engine import get_conn

router = APIRouter(tags=["anchoring"])

BATCH_SQL = """
SELECT b.id, b.merkle_root, b.leaf_count, b.risk_level::text AS risk_level, b.status::text AS status, b.attempts,
       b.last_error, b.created_at, b.confirmed_at, t.tx_hash, t.network, t.chain_id, t.contract_address, t.block_number,
       t.block_timestamp, t.gas_used, t.fee_native::text AS fee_native, t.fee_inr::text AS fee_inr,
       (SELECT count(DISTINCT e.inspection_id) FROM anchor_items ai JOIN inspection_events e ON e.id=ai.event_id
        WHERE ai.batch_id=b.id) AS inspections
FROM anchor_batches b
LEFT JOIN LATERAL (SELECT * FROM blockchain_txs bt WHERE bt.batch_id=b.id ORDER BY bt.id DESC LIMIT 1) t ON true
"""


def _batch(r) -> dict:
    d = dict(r)
    for k in ("created_at", "confirmed_at", "block_timestamp"):
        d[k] = iso(d[k])
    base = EXPLORERS.get(d["chain_id"]) if d["chain_id"] else None
    d["explorer_url"] = f"{base}/tx/{d['tx_hash']}" if base and d["tx_hash"] else None
    return d


@router.get("/anchors")
def list_anchors(status: str | None = None, risk: str | None = None, limit: int = Query(default=50, le=500),
                 offset: int = 0, _: CurrentUser = Depends(ALL_ROLES), conn: Connection = Depends(get_conn)):
    where, p = [], {}
    if status:
        where.append("b.status::text=:s")
        p["s"] = status
    if risk:
        where.append("b.risk_level::text=:r")
        p["r"] = risk
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(text(BATCH_SQL + clause + " ORDER BY b.id DESC LIMIT :l OFFSET :o"),
                        {**p, "l": limit, "o": offset}).mappings().all()
    total = conn.execute(text("SELECT count(*) FROM anchor_batches b" + clause), p).scalar_one()
    queued = {r[0]: r[1] for r in conn.execute(text(
        "SELECT risk_level::text, count(*) FROM anchor_queue WHERE batch_id IS NULL GROUP BY 1"))}
    return {"total": total, "queued": queued, "items": [_batch(r) for r in rows]}


@router.get("/anchors/{batch_id}")
def get_anchor(batch_id: int, _: CurrentUser = Depends(ALL_ROLES), conn: Connection = Depends(get_conn)):
    r = conn.execute(text(BATCH_SQL + " WHERE b.id=:b"), {"b": batch_id}).mappings().first()
    if not r:
        raise not_found("anchor batch")
    items = conn.execute(text("""
        SELECT ai.leaf_index, ai.leaf_hash, ai.merkle_proof, e.id AS event_id, e.seq, e.event_type::text AS event_type,
               e.event_hash, l.code AS line, i.id::text AS inspection_id, i.inspection_code
        FROM anchor_items ai JOIN inspection_events e ON e.id=ai.event_id JOIN production_lines l ON l.id=e.line_id
        JOIN inspections i ON i.id=e.inspection_id WHERE ai.batch_id=:b ORDER BY ai.leaf_index
    """), {"b": batch_id}).mappings().all()
    return {**_batch(r), "items": [dict(i) for i in items]}


@router.get("/chain/info")
def chain_info(_: CurrentUser = Depends(ALL_ROLES)):
    s = get_settings()
    c = get_chain()
    info = {"chain": s.chain, "network": None, "chain_id": None, "contract_address": None, "explorer": None,
            "onchain_anchor_count": None, "reachable": False}
    if c:
        info.update(network=c.network, chain_id=c.chain_id, contract_address=c.contract_address,
                    explorer=EXPLORERS.get(c.chain_id))
        try:
            info["onchain_anchor_count"] = c.anchor_count()
            info["reachable"] = True
        except Exception as e:  # node down
            info["error"] = str(e)[:200]
    return info


@router.get("/chain/txs")
def chain_txs(limit: int = Query(default=50, le=500), _: CurrentUser = Depends(ALL_ROLES),
              conn: Connection = Depends(get_conn)):
    rows = conn.execute(text(
        "SELECT t.id, t.batch_id, t.network, t.chain_id, t.contract_address, t.tx_hash, t.block_number, "
        "t.block_timestamp, t.gas_used, t.effective_gas_price_wei::text AS effective_gas_price_wei, "
        "t.fee_native::text AS fee_native, t.fee_inr::text AS fee_inr, b.leaf_count, b.risk_level::text AS risk_level, "
        "b.merkle_root FROM blockchain_txs t JOIN anchor_batches b ON b.id=t.batch_id ORDER BY t.id DESC LIMIT :l"
    ), {"l": limit}).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        d["block_timestamp"] = iso(d["block_timestamp"])
        base = EXPLORERS.get(d["chain_id"])
        d["explorer_url"] = f"{base}/tx/{d['tx_hash']}" if base else None
        out.append(d)
    return out


# ---------------- alerts ----------------

class AlertPatch(BaseModel):
    status: str


@router.get("/alerts")
def list_alerts(status: str | None = None, alert_type: str | None = Query(default=None, alias="type"),
                limit: int = Query(default=100, le=500), _: CurrentUser = Depends(ALL_ROLES),
                conn: Connection = Depends(get_conn)):
    where, p = [], {}
    if status:
        where.append("a.status::text=:s")
        p["s"] = status
    if alert_type:
        where.append("a.alert_type::text=:t")
        p["t"] = alert_type
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(text(
        "SELECT a.id::text, a.alert_type::text AS alert_type, a.severity::text AS severity, a.status::text AS status, "
        "a.details, a.created_at, a.resolved_at, i.inspection_code, a.inspection_id::text AS inspection_id, "
        "u.employee_code AS resolved_by FROM alerts a LEFT JOIN inspections i ON i.id=a.inspection_id "
        "LEFT JOIN users u ON u.id=a.resolved_by" + clause + " ORDER BY a.created_at DESC LIMIT :l"
    ), {**p, "l": limit}).mappings().all()
    counts = {f"{r[0]}:{r[1]}": r[2] for r in conn.execute(text(
        "SELECT alert_type::text, status::text, count(*) FROM alerts GROUP BY 1, 2"))}
    return {"items": [{**dict(r), "created_at": iso(r["created_at"]), "resolved_at": iso(r["resolved_at"])}
                      for r in rows], "counts": counts}


@router.patch("/alerts/{alert_id}")
def patch_alert(alert_id: str, body: AlertPatch,
                user: CurrentUser = Depends(require_roles("QUALITY_ENGINEER", "QUALITY_MANAGER", "ADMIN")),
                conn: Connection = Depends(get_conn)):
    if body.status not in ("ACKNOWLEDGED", "RESOLVED", "OPEN"):
        raise ApiError(422, "BAD_STATUS", "status must be OPEN, ACKNOWLEDGED or RESOLVED")
    n = conn.execute(text(
        "UPDATE alerts SET status=CAST(:s AS alert_status_t), resolved_by=CASE WHEN :s='RESOLVED' THEN "
        "CAST(:u AS uuid) ELSE resolved_by END, resolved_at=CASE WHEN :s='RESOLVED' THEN :t ELSE resolved_at END "
        "WHERE id::text=:i"
    ), {"s": body.status, "u": user.id, "t": now_ms(), "i": alert_id}).rowcount
    if not n:
        raise not_found("alert")
    return {"id": alert_id, "status": body.status}
