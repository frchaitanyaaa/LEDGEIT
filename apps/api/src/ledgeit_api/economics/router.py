"""Economics (CHAITANYA.md §5.10): real fees from tx receipts, cost per inspection, batching savings."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import Connection, text

from ..auth.deps import CurrentUser, require_roles
from ..core.yamlconf import economics_config
from ..db.engine import get_conn

router = APIRouter(tags=["economics"])
Q4 = Decimal("0.0001")


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


@router.get("/economics")
def economics(_: CurrentUser = Depends(require_roles("QUALITY_MANAGER", "ADMIN", "AUDITOR")),
              conn: Connection = Depends(get_conn)):
    econ = economics_config()
    tx = conn.execute(text(
        "SELECT count(*) AS txs, COALESCE(sum(gas_used),0) AS gas, COALESCE(sum(fee_native),0) AS fee_native, "
        "COALESCE(sum(fee_inr),0) AS fee_inr, COALESCE(avg(gas_used),0) AS avg_gas, "
        "COALESCE(avg(fee_inr),0) AS avg_fee_inr FROM blockchain_txs")).mappings().one()
    covered = conn.execute(text(
        "SELECT count(DISTINCT e.inspection_id) AS inspections, count(*) AS events FROM anchor_items ai "
        "JOIN anchor_batches b ON b.id=ai.batch_id JOIN inspection_events e ON e.id=ai.event_id "
        "WHERE b.status='CONFIRMED'")).mappings().one()
    by_risk = conn.execute(text(
        "SELECT b.risk_level::text AS risk, count(DISTINCT b.id) AS batches, sum(b.leaf_count) AS leaves, "
        "COALESCE(sum(t.fee_inr),0) AS fee_inr, COALESCE(avg(b.leaf_count),0) AS avg_batch FROM anchor_batches b "
        "LEFT JOIN blockchain_txs t ON t.batch_id=b.id WHERE b.status='CONFIRMED' GROUP BY 1 ORDER BY 1"
    )).mappings().all()
    daily = conn.execute(text(
        "SELECT to_char(date_trunc('day', created_at), 'YYYY-MM-DD') AS day, count(*) AS txs, "
        "COALESCE(sum(fee_inr),0) AS fee_inr FROM blockchain_txs GROUP BY 1 ORDER BY 1")).mappings().all()
    storage_bytes = conn.execute(text("SELECT COALESCE(sum(size_bytes),0) FROM evidence")).scalar_one()
    total_inspections = conn.execute(text("SELECT count(*) FROM inspections")).scalar_one()

    fee_inr, avg_fee = _d(tx["fee_inr"]), _d(tx["avg_fee_inr"])
    n_insp, n_events = covered["inspections"], covered["events"]
    per_insp = (fee_inr / n_insp).quantize(Q4) if n_insp else None
    # Counterfactuals priced at the observed average fee per transaction
    no_batch_per_event = (avg_fee * n_events).quantize(Q4)
    no_batch_per_insp = (avg_fee * n_insp).quantize(Q4)
    savings = (Decimal(1) - fee_inr / no_batch_per_event) * 100 if no_batch_per_event else None
    storage_gb = Decimal(storage_bytes) / Decimal(1024**3)
    storage_inr = (storage_gb * _d(econ["storage_inr_per_gb_month"])).quantize(Q4)
    compute_inr = (_d(econ["compute_inr_per_inspection"]) * total_inspections).quantize(Q4)
    return {
        "currency": "INR", "native_symbol": econ.get("native_symbol", "POL"), "native_to_inr": econ["native_to_inr"],
        "chain": {"transactions": tx["txs"], "gas_used": int(tx["gas"]), "avg_gas_per_tx": int(tx["avg_gas"]),
                  "fee_native": str(_d(tx["fee_native"]).normalize()), "fee_inr": str(fee_inr.quantize(Q4)),
                  "avg_fee_inr_per_tx": str(avg_fee.quantize(Q4))},
        "coverage": {"inspections_anchored": n_insp, "events_anchored": n_events,
                     "events_per_tx": round(n_events / tx["txs"], 2) if tx["txs"] else None},
        "cost_per_inspection_inr": str(per_insp) if per_insp is not None else None,
        "batching": {"actual_inr": str(fee_inr.quantize(Q4)),
                     "without_batching_one_tx_per_event_inr": str(no_batch_per_event),
                     "without_batching_one_tx_per_inspection_inr": str(no_batch_per_insp),
                     "savings_percent": f"{savings:.1f}" if savings is not None else None},
        "by_risk": [{**dict(r), "leaves": int(r["leaves"] or 0), "fee_inr": str(_d(r["fee_inr"]).quantize(Q4)),
                     "avg_batch": float(round(r["avg_batch"], 1))} for r in by_risk],
        "daily": [{**dict(r), "fee_inr": str(_d(r["fee_inr"]).quantize(Q4))} for r in daily],
        "other_costs": {"evidence_storage_gb": f"{storage_gb:.6f}", "storage_inr_per_month": str(storage_inr),
                        "compute_inr": str(compute_inr)},
    }
