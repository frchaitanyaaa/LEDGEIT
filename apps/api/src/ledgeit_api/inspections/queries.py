"""Read-side helpers shared by the inspections, verification, reports and public routers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import Connection, text

from ..core.config import get_settings
from ..core.errors import not_found
from ..core.time import iso

LIST_SQL = """
SELECT i.id::text AS id, i.inspection_code, i.unit_serial, b.batch_code, l.code AS line, d.device_code AS device,
       i.decision::text AS decision, i.defect_class, i.severity::text AS severity, i.confidence::text AS confidence,
       i.risk_level::text AS risk_level, i.record_hash, i.inspected_at, m.name AS model_name, m.version AS model_version,
       s.status, s.final_decision::text AS final_decision, s.anchor_status::text AS anchor_status,
       s.last_verification::text AS last_verification
FROM inspections i
JOIN inspection_status s ON s.inspection_id = i.id
JOIN batches b ON b.id = i.batch_id
JOIN production_lines l ON l.id = i.line_id
JOIN devices d ON d.id = i.device_id
JOIN ai_models m ON m.id = i.model_id
"""


def resolve_inspection_id(conn: Connection, id_or_code: str) -> str:
    row = conn.execute(text(
        "SELECT id::text FROM inspections WHERE id::text=:x OR inspection_code=:x"
    ), {"x": id_or_code}).scalar()
    if not row:
        raise not_found("inspection")
    return row


def evidence_token(evidence_id: str, minutes: int = 60) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode({"sub": evidence_id, "type": "evidence", "exp": exp}, get_settings().jwt_secret, "HS256")


def evidence_url(evidence_id: str | None) -> str | None:
    if not evidence_id:
        return None
    return f"/api/v1/evidence/{evidence_id}/content?token={evidence_token(evidence_id)}"


def list_row(r) -> dict:
    d = dict(r)
    d["inspected_at"] = iso(d["inspected_at"])
    return d


def timeline(conn: Connection, inspection_id: str) -> list[dict]:
    rows = conn.execute(text("""
        SELECT e.id, e.seq, e.event_type::text AS event_type, e.actor_type::text AS actor_type, e.actor_id,
               e.payload, e.payload_hash, e.prev_event_hash, e.event_hash, e.signature, e.created_at,
               ai.batch_id, ab.merkle_root, ab.status::text AS anchor_status, ai.leaf_index,
               t.tx_hash, t.network, t.block_number, q.risk_level::text AS queued_risk
        FROM inspection_events e
        LEFT JOIN anchor_items ai ON ai.event_id = e.id
        LEFT JOIN anchor_batches ab ON ab.id = ai.batch_id
        LEFT JOIN LATERAL (SELECT tx_hash, network, block_number FROM blockchain_txs bt
                           WHERE bt.batch_id = ab.id ORDER BY bt.id DESC LIMIT 1) t ON true
        LEFT JOIN anchor_queue q ON q.event_id = e.id
        WHERE e.inspection_id = :i ORDER BY e.seq
    """), {"i": inspection_id}).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        d["created_at"] = iso(d["created_at"])
        d["anchor"] = None if d["batch_id"] is None else {
            "batch_id": d["batch_id"], "merkle_root": d["merkle_root"], "status": d["anchor_status"],
            "leaf_index": d["leaf_index"], "tx_hash": d["tx_hash"], "network": d["network"],
            "block_number": d["block_number"],
        }
        for k in ("batch_id", "merkle_root", "anchor_status", "leaf_index", "tx_hash", "network", "block_number"):
            d.pop(k)
        out.append(d)
    return out


def detail(conn: Connection, inspection_id: str) -> dict:
    row = conn.execute(text(LIST_SQL + " WHERE i.id = :i"), {"i": inspection_id}).mappings().first()
    if not row:
        raise not_found("inspection")
    extra = conn.execute(text("""
        SELECT i.canonical_record, i.device_signature, i.explanation, i.risk_reasons, i.created_at,
               i.evidence_id::text AS evidence_id, i.heatmap_evidence_id::text AS heatmap_evidence_id,
               m.id::text AS model_id, m.weights_sha256, m.status::text AS model_status, m.framework,
               m.dataset_version, m.approved_at, p.sku AS product_sku, p.name AS product_name, p.is_regulated,
               d.public_key AS device_public_key
        FROM inspections i JOIN ai_models m ON m.id=i.model_id JOIN batches b ON b.id=i.batch_id
        JOIN products p ON p.id=b.product_id JOIN devices d ON d.id=i.device_id WHERE i.id=:i
    """), {"i": inspection_id}).mappings().one()
    ev = conn.execute(text(
        "SELECT id::text, kind, sha256, phash, mime_type, size_bytes, width, height, storage_uri FROM evidence "
        "WHERE id IN (:a, :b)"
    ), {"a": extra["evidence_id"], "b": extra["heatmap_evidence_id"] or extra["evidence_id"]}).mappings().all()
    overrides = conn.execute(text("""
        SELECT o.id::text, o.original_decision::text AS original_decision, o.original_confidence::text AS original_confidence,
               o.new_decision::text AS new_decision, o.reason_code, o.reason_text, o.reviewed_evidence,
               u.employee_code AS operator, u.full_name AS operator_name, o.payload_hash, o.operator_signature,
               o.created_at, a.approved, a.comment AS approval_comment, au.employee_code AS approver,
               a.created_at AS approved_at
        FROM overrides o JOIN users u ON u.id=o.operator_id
        LEFT JOIN override_approvals a ON a.override_id=o.id LEFT JOIN users au ON au.id=a.approver_id
        WHERE o.inspection_id=:i ORDER BY o.created_at
    """), {"i": inspection_id}).mappings().all()
    alerts = conn.execute(text(
        "SELECT id::text, alert_type::text AS alert_type, severity::text AS severity, status::text AS status, details, "
        "created_at FROM alerts WHERE inspection_id=:i ORDER BY created_at DESC"
    ), {"i": inspection_id}).mappings().all()
    ver = conn.execute(text(
        "SELECT id::text, result::text AS result, checks, verified_at FROM verifications WHERE inspection_id=:i "
        "ORDER BY verified_at DESC LIMIT 1"
    ), {"i": inspection_id}).mappings().first()
    evidence = []
    for e in ev:
        d = dict(e)
        d["url"] = evidence_url(d["id"])
        evidence.append(d)
    out = list_row(row)
    out.update({
        "record": extra["canonical_record"],
        "device_signature": extra["device_signature"],
        "device_public_key": extra["device_public_key"],
        "explanation": extra["explanation"],
        "risk_reasons": list(extra["risk_reasons"]),
        "created_at": iso(extra["created_at"]),
        "model": {"id": extra["model_id"], "name": row["model_name"], "version": row["model_version"],
                  "weights_sha256": extra["weights_sha256"], "status": extra["model_status"],
                  "framework": extra["framework"], "dataset_version": extra["dataset_version"],
                  "approved_at": iso(extra["approved_at"])},
        "product": {"sku": extra["product_sku"], "name": extra["product_name"], "is_regulated": extra["is_regulated"]},
        "evidence": evidence,
        "overrides": [{**dict(o), "created_at": iso(o["created_at"]), "approved_at": iso(o["approved_at"])}
                      for o in overrides],
        "alerts": [{**dict(a), "created_at": iso(a["created_at"])} for a in alerts],
        "latest_verification": None if not ver else {**dict(ver), "verified_at": iso(ver["verified_at"])},
    })
    return out
