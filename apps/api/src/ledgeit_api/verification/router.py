from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Connection, text

from ..auth.deps import ALL_ROLES, CurrentUser
from ..chain.client import EXPLORERS, get_chain
from ..core.config import get_settings
from ..core.errors import not_found
from ..core.time import iso
from ..db.engine import get_conn, get_engine
from ..inspections.queries import resolve_inspection_id
from ..services.storage import get_storage
from .engine import _events, verify_inspection

router = APIRouter(tags=["verification"])


@router.post("/inspections/{id_or_code}/verify", summary="Run the 5 integrity checks")
def verify(id_or_code: str, user: CurrentUser = Depends(ALL_ROLES)):
    with get_engine().begin() as conn:
        iid = resolve_inspection_id(conn, id_or_code)
        return verify_inspection(conn, iid, storage=get_storage(), chain=get_chain(), requested_by=user.id)


@router.post("/verify/batch", summary="Verify many inspections (Verification Center)")
def verify_many(line: str | None = None, batch: str | None = None, limit: int = Query(default=50, le=500),
                user: CurrentUser = Depends(ALL_ROLES)):
    where, p = [], {"l": limit}
    if line:
        where.append("l.code=:line")
        p["line"] = line
    if batch:
        where.append("b.batch_code=:batch")
        p["batch"] = batch
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    with get_engine().begin() as conn:
        ids = [r[0] for r in conn.execute(text(
            "SELECT i.id::text FROM inspections i JOIN production_lines l ON l.id=i.line_id JOIN batches b "
            "ON b.id=i.batch_id" + clause + " ORDER BY i.inspected_at DESC LIMIT :l"), p)]
    results = []
    storage, chain = get_storage(), get_chain()
    for iid in ids:
        with get_engine().begin() as conn:
            r = verify_inspection(conn, iid, storage=storage, chain=chain, requested_by=user.id)
        results.append({"inspection_id": iid, "inspection_code": r["inspection_code"], "result": r["result"],
                        "failed": [k for k, v in r["checks"].items() if v["status"] == "FAIL"]})
    summary = {k: sum(1 for r in results if r["result"] == k) for k in ("VERIFIED", "PENDING_ANCHOR", "FAILED")}
    return {"summary": summary, "results": results}


@router.get("/verifications")
def list_verifications(result: str | None = None, limit: int = Query(default=50, le=500),
                       _: CurrentUser = Depends(ALL_ROLES), conn: Connection = Depends(get_conn)):
    where, p = "", {"l": limit}
    if result:
        where, p["r"] = " WHERE v.result::text=:r", result
    rows = conn.execute(text(
        "SELECT v.id::text, v.result::text AS result, v.checks, v.verified_at, i.inspection_code, "
        "i.id::text AS inspection_id, u.employee_code AS requested_by FROM verifications v "
        "JOIN inspections i ON i.id=v.inspection_id LEFT JOIN users u ON u.id=v.requested_by" + where +
        " ORDER BY v.verified_at DESC LIMIT :l"), p).mappings().all()
    return [{**dict(r), "verified_at": iso(r["verified_at"]),
             "checks": {k: v["status"] for k, v in r["checks"].items()}} for r in rows]


# ---------------- public (QR target) ----------------

public = APIRouter(prefix="/public", tags=["public"])


def public_rpc_url() -> str | None:
    s = get_settings()
    if s.public_rpc_url:
        return s.public_rpc_url
    return {"local": "http://localhost:8545", "amoy": s.rpc_url_amoy}.get(s.chain)


@public.get("/verify/{code}", summary="Public verification (no login). Images are never exposed.")
def public_verify(code: str):
    with get_engine().begin() as conn:
        rep = conn.execute(text("SELECT params, report_type, created_at, file_sha256 FROM reports "
                                "WHERE verification_code=:c"), {"c": code}).mappings().first()
        if rep:
            from ..reports.service import public_report_verification

            return public_report_verification(conn, code)
        iid = conn.execute(text("SELECT id::text FROM inspections WHERE inspection_code=:c OR record_hash=:c"),
                           {"c": code}).scalar()
        if not iid:
            raise not_found("verification code")
        chain = get_chain()
        result = verify_inspection(conn, iid, storage=get_storage(), chain=chain, requested_by=None)
        return {"kind": "inspection", **public_inspection_view(conn, iid, result, chain)}


def public_inspection_view(conn: Connection, iid: str, result: dict, chain) -> dict:
    row = conn.execute(text("""
        SELECT i.inspection_code, i.unit_serial, b.batch_code, l.code AS line, p.name AS product,
               i.decision::text AS ai_decision, i.confidence::text AS confidence, i.severity::text AS severity,
               i.defect_class, s.status, s.final_decision::text AS final_decision, m.name AS model_name,
               m.version AS model_version, i.inspected_at, i.record_hash, i.canonical_record
        FROM inspections i JOIN batches b ON b.id=i.batch_id JOIN products p ON p.id=b.product_id
        JOIN production_lines l ON l.id=i.line_id JOIN inspection_status s ON s.inspection_id=i.id
        JOIN ai_models m ON m.id=i.model_id WHERE i.id=:i
    """), {"i": iid}).mappings().one()
    events = _events(conn, "inspection_id=:i", {"i": iid})
    proofs = []
    for e in events:
        item = conn.execute(text(
            "SELECT ai.leaf_hash, ai.merkle_proof, b.merkle_root, b.id AS batch_id, t.tx_hash, t.block_number "
            "FROM anchor_items ai JOIN anchor_batches b ON b.id=ai.batch_id LEFT JOIN LATERAL (SELECT tx_hash, "
            "block_number FROM blockchain_txs bt WHERE bt.batch_id=b.id ORDER BY id DESC LIMIT 1) t ON true "
            "WHERE ai.event_id=:e"), {"e": e["id"]}).mappings().first()
        proofs.append({
            "seq": e["seq"], "event_type": e["event_type"], "actor_type": e["actor_type"], "actor_id": e["actor_id"],
            "payload": e["payload"], "payload_hash": e["payload_hash"], "prev_event_hash": e["prev_event_hash"],
            "event_hash": e["event_hash"], "created_at": e["created_at"],
            "anchor": dict(item) if item else None,
        })
    explorer = EXPLORERS.get(chain.chain_id) if chain else None
    checks = {k: {"status": v["status"], "title": v["title"], "problems": v["problems"]}
              for k, v in result["checks"].items()}
    d = dict(row)
    d["inspected_at"] = iso(d["inspected_at"])
    record = d.pop("canonical_record")
    return {
        "result": result["result"], "message": result["message"], "verified_at": result.get("verified_at"),
        "inspection": d, "record": record, "checks": checks,
        "proof": {"line": row["line"], "events": proofs,
                  "chain": None if not chain else {
                      "network": chain.network, "chain_id": chain.chain_id, "contract_address": chain.contract_address,
                      "rpc_url": public_rpc_url(), "explorer": explorer}},
    }
