"""Master data + AI Model Registry: lines, devices, products, batches, models."""

from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import Connection, text

from ledgeit_proof import ZERO_HASH

from ..auth.deps import ALL_ROLES, CurrentUser, require_roles
from ..core.errors import ApiError, not_found
from ..core.time import iso, now_ms
from ..db.engine import get_conn
from ..db.json import jdump

router = APIRouter(tags=["registry"])


def _iso_rows(rows, *keys):
    out = []
    for r in rows:
        d = dict(r)
        for k in keys:
            d[k] = iso(d[k])
        out.append(d)
    return out


@router.get("/lines")
def lines(_: CurrentUser = Depends(ALL_ROLES), conn: Connection = Depends(get_conn)):
    rows = conn.execute(text("""
        SELECT l.id::text, l.code, l.name, p.name AS plant, l.genesis_hash, h.last_seq, h.last_event_hash, h.updated_at,
               (SELECT count(*) FROM inspections i WHERE i.line_id=l.id) AS inspections
        FROM production_lines l JOIN plants p ON p.id=l.plant_id JOIN line_heads h ON h.line_id=l.id ORDER BY l.code
    """)).mappings().all()
    return _iso_rows(rows, "updated_at")


@router.get("/devices")
def devices(_: CurrentUser = Depends(ALL_ROLES), conn: Connection = Depends(get_conn)):
    rows = conn.execute(text("""
        SELECT d.id::text, d.device_code, d.device_type, d.public_key, d.is_active, d.registered_at, l.code AS line,
               (SELECT max(i.created_at) FROM inspections i WHERE i.device_id=d.id) AS last_seen,
               (SELECT count(*) FROM inspections i WHERE i.device_id=d.id) AS inspections
        FROM devices d JOIN production_lines l ON l.id=d.line_id ORDER BY d.device_code
    """)).mappings().all()
    return _iso_rows(rows, "registered_at", "last_seen")


@router.get("/devices/{device_code}/head", summary="Device's last record hash (public; used by edge devices)")
def device_head(device_code: str, conn: Connection = Depends(get_conn)):
    dev = conn.execute(text(
        "SELECT d.id, l.code FROM devices d JOIN production_lines l ON l.id=d.line_id WHERE device_code=:c"
    ), {"c": device_code}).first()
    if not dev:
        raise not_found("device")
    row = conn.execute(text(
        "SELECT record_hash, inspection_code FROM inspections WHERE device_id=:d ORDER BY created_at DESC, id DESC LIMIT 1"
    ), {"d": dev[0]}).first()
    count = conn.execute(text("SELECT count(*) FROM inspections WHERE device_id=:d"), {"d": dev[0]}).scalar_one()
    return {"device": device_code, "line": dev[1], "last_record_hash": row[0] if row else ZERO_HASH,
            "last_inspection_code": row[1] if row else None, "count": count}


@router.get("/products")
def products(_: CurrentUser = Depends(ALL_ROLES), conn: Connection = Depends(get_conn)):
    return [dict(r) for r in conn.execute(text(
        "SELECT id::text, sku, name, is_regulated FROM products ORDER BY sku")).mappings()]


@router.get("/batches")
def batches(_: CurrentUser = Depends(ALL_ROLES), conn: Connection = Depends(get_conn)):
    rows = conn.execute(text("""
        SELECT b.id::text, b.batch_code, p.sku AS product_sku, p.is_regulated, l.code AS line, b.started_at, b.ended_at,
               count(i.id) AS inspections, count(i.id) FILTER (WHERE i.decision='FAIL') AS ai_fail
        FROM batches b JOIN products p ON p.id=b.product_id JOIN production_lines l ON l.id=b.line_id
        LEFT JOIN inspections i ON i.batch_id=b.id GROUP BY b.id, p.sku, p.is_regulated, l.code ORDER BY b.started_at DESC
    """)).mappings().all()
    return _iso_rows(rows, "started_at", "ended_at")


# ---------------- AI Model Registry ----------------

class ModelIn(BaseModel):
    name: str
    version: str
    weights_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    framework: str
    dataset_version: str
    training_date: date | None = None
    metrics: dict = Field(default_factory=dict)
    environment: str = "demo"


MODEL_SQL = """
SELECT m.id::text, m.name, m.version, m.weights_sha256, m.framework, m.dataset_version, m.training_date, m.metrics,
       m.status::text AS status, m.approved_at, m.retired_at, m.deployed_at, m.environment, m.created_at,
       ua.employee_code AS approved_by, ur.employee_code AS registered_by,
       (SELECT count(*) FROM inspections i WHERE i.model_id=m.id) AS inspections,
       (SELECT count(*) FROM inspections i WHERE i.model_id=m.id AND i.decision='FAIL') AS ai_fail,
       (SELECT count(*) FROM overrides o JOIN inspections i ON i.id=o.inspection_id WHERE i.model_id=m.id) AS overrides,
       (SELECT count(*) FROM overrides o JOIN inspections i ON i.id=o.inspection_id
         WHERE i.model_id=m.id AND o.original_decision='FAIL' AND o.new_decision='PASS') AS false_positives,
       (SELECT count(*) FROM overrides o JOIN inspections i ON i.id=o.inspection_id
         WHERE i.model_id=m.id AND o.original_decision='PASS' AND o.new_decision='FAIL') AS false_negatives,
       (SELECT avg(i.confidence)::numeric(5,4)::text FROM inspections i WHERE i.model_id=m.id) AS avg_confidence
FROM ai_models m LEFT JOIN users ua ON ua.id=m.approved_by LEFT JOIN users ur ON ur.id=m.registered_by
"""


def _model_out(r) -> dict:
    d = dict(r)
    for k in ("approved_at", "retired_at", "deployed_at", "created_at"):
        d[k] = iso(d[k])
    d["training_date"] = d["training_date"].isoformat() if d["training_date"] else None
    n = d["inspections"] or 0
    d["override_rate"] = f"{(d['overrides'] / n):.4f}" if n else None
    # Human-derived error rates: FP = AI said FAIL, human overrode to PASS; FN = AI said PASS, human overrode to FAIL.
    d["fp_rate"] = f"{(d['false_positives'] / d['ai_fail']):.4f}" if d["ai_fail"] else None
    ai_pass = n - (d["ai_fail"] or 0)
    d["fn_rate"] = f"{(d['false_negatives'] / ai_pass):.4f}" if ai_pass else None
    return d


@router.get("/models")
def list_models(_: CurrentUser = Depends(ALL_ROLES), conn: Connection = Depends(get_conn)):
    return [_model_out(r) for r in conn.execute(text(MODEL_SQL + " ORDER BY m.name, m.version")).mappings()]


@router.post("/models", status_code=201)
def register_model(body: ModelIn, user: CurrentUser = Depends(require_roles("ADMIN")),
                   conn: Connection = Depends(get_conn)):
    if not re.match(r"^[\w.\-]+$", body.version):
        raise ApiError(422, "BAD_VERSION", "version must be alphanumeric with dots/dashes")
    exists = conn.execute(text("SELECT 1 FROM ai_models WHERE name=:n AND version=:v"),
                          {"n": body.name, "v": body.version}).first()
    if exists:
        raise ApiError(409, "CONFLICT", "model version already registered (identity is immutable)")
    mid = conn.execute(text(
        "INSERT INTO ai_models(name, version, weights_sha256, framework, dataset_version, training_date, metrics, "
        "environment, registered_by) VALUES (:n, :v, :w, :f, :d, :t, CAST(:m AS jsonb), :e, :u) RETURNING id::text"
    ), {"n": body.name, "v": body.version, "w": body.weights_sha256, "f": body.framework, "d": body.dataset_version,
        "t": body.training_date, "m": jdump(body.metrics), "e": body.environment, "u": user.id}).scalar_one()
    return _model_out(conn.execute(text(MODEL_SQL + " WHERE m.id=:i"), {"i": mid}).mappings().one())


@router.post("/models/{model_id}/approve")
def approve_model(model_id: str, user: CurrentUser = Depends(require_roles("QUALITY_MANAGER", "ADMIN")),
                  conn: Connection = Depends(get_conn)):
    n = conn.execute(text(
        "UPDATE ai_models SET status='APPROVED', approved_by=:u, approved_at=:t, deployed_at=COALESCE(deployed_at, :t), "
        "retired_at=NULL WHERE id::text=:i AND status<>'APPROVED'"
    ), {"u": user.id, "t": now_ms(), "i": model_id}).rowcount
    if not n and not conn.execute(text("SELECT 1 FROM ai_models WHERE id::text=:i"), {"i": model_id}).first():
        raise not_found("model")
    return _model_out(conn.execute(text(MODEL_SQL + " WHERE m.id::text=:i"), {"i": model_id}).mappings().one())


@router.post("/models/{model_id}/retire")
def retire_model(model_id: str, _: CurrentUser = Depends(require_roles("QUALITY_MANAGER", "ADMIN")),
                 conn: Connection = Depends(get_conn)):
    n = conn.execute(text("UPDATE ai_models SET status='RETIRED', retired_at=:t WHERE id::text=:i"),
                     {"t": now_ms(), "i": model_id}).rowcount
    if not n:
        raise not_found("model")
    return _model_out(conn.execute(text(MODEL_SQL + " WHERE m.id::text=:i"), {"i": model_id}).mappings().one())
