"""Executive dashboard KPIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import Connection, text

from ..auth.deps import ALL_ROLES, CurrentUser
from ..core.time import iso
from ..db.engine import get_conn

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary")
def summary(_: CurrentUser = Depends(ALL_ROLES), conn: Connection = Depends(get_conn)):
    k = conn.execute(text("""
        SELECT count(*) AS inspections,
               count(*) FILTER (WHERE i.inspected_at >= now() - interval '24 hours') AS last_24h,
               count(*) FILTER (WHERE i.decision='PASS') AS ai_pass,
               count(*) FILTER (WHERE i.decision='FAIL') AS ai_fail,
               count(*) FILTER (WHERE s.status='PENDING_REVIEW') AS pending_review,
               count(*) FILTER (WHERE s.status='PENDING_APPROVAL') AS pending_approval,
               count(*) FILTER (WHERE s.status='DISPUTED') AS disputed,
               count(*) FILTER (WHERE s.final_decision='PASS') AS released,
               count(*) FILTER (WHERE s.final_decision='FAIL') AS rejected,
               count(*) FILTER (WHERE s.anchor_status='CONFIRMED') AS anchored,
               count(*) FILTER (WHERE s.last_verification='VERIFIED') AS verified,
               count(*) FILTER (WHERE s.last_verification='FAILED') AS verification_failed,
               count(*) FILTER (WHERE i.risk_level='HIGH') AS high_risk,
               avg(i.confidence)::numeric(5,4)::text AS avg_confidence
        FROM inspections i JOIN inspection_status s ON s.inspection_id=i.id
    """)).mappings().one()
    overrides = conn.execute(text("SELECT count(*) FROM overrides")).scalar_one()
    alerts = {f"{r[0]}": r[1] for r in conn.execute(text(
        "SELECT severity::text, count(*) FROM alerts WHERE status<>'RESOLVED' GROUP BY 1"))}
    alert_types = [{"type": r[0], "count": r[1]} for r in conn.execute(text(
        "SELECT alert_type::text, count(*) FROM alerts WHERE status<>'RESOLVED' GROUP BY 1 ORDER BY 2 DESC"))]
    hourly = conn.execute(text("""
        SELECT to_char(date_trunc('hour', inspected_at), 'YYYY-MM-DD"T"HH24:00') AS hour,
               count(*) FILTER (WHERE decision='PASS') AS pass, count(*) FILTER (WHERE decision='FAIL') AS fail
        FROM inspections WHERE inspected_at >= now() - interval '24 hours' GROUP BY 1 ORDER BY 1
    """)).mappings().all()
    by_class = conn.execute(text(
        "SELECT COALESCE(defect_class, 'none') AS defect_class, count(*) FROM inspections WHERE decision='FAIL' "
        "GROUP BY 1 ORDER BY 2 DESC")).mappings().all()
    by_line = conn.execute(text("""
        SELECT l.code AS line, count(i.id) AS inspections, count(i.id) FILTER (WHERE i.decision='FAIL') AS fail,
               h.last_seq AS chain_length
        FROM production_lines l JOIN line_heads h ON h.line_id=l.id LEFT JOIN inspections i ON i.line_id=l.id
        GROUP BY l.code, h.last_seq ORDER BY l.code
    """)).mappings().all()
    by_model = conn.execute(text("""
        SELECT m.name || '@' || m.version AS model, m.status::text AS status, count(i.id) AS inspections,
               (SELECT count(*) FROM overrides o JOIN inspections ii ON ii.id=o.inspection_id WHERE ii.model_id=m.id)
               AS overrides, avg(i.confidence)::numeric(5,4)::text AS avg_confidence
        FROM ai_models m LEFT JOIN inspections i ON i.model_id=m.id GROUP BY m.id ORDER BY 1
    """)).mappings().all()
    risk = {r[0]: r[1] for r in conn.execute(text(
        "SELECT risk_level::text, count(*) FROM inspections GROUP BY 1"))}
    anchor = conn.execute(text(
        "SELECT count(*) FILTER (WHERE status='CONFIRMED') AS confirmed, count(*) FILTER (WHERE status IN "
        "('PENDING','SUBMITTED')) AS pending, count(*) FILTER (WHERE status='FAILED') AS failed, "
        "max(confirmed_at) AS last_confirmed FROM anchor_batches")).mappings().one()
    queued = conn.execute(text("SELECT count(*) FROM anchor_queue WHERE batch_id IS NULL")).scalar_one()
    n = k["inspections"] or 0
    reviewed = (k["released"] or 0) + (k["rejected"] or 0)
    return {
        "kpis": {**dict(k), "overrides": overrides,
                 "fail_rate": f"{k['ai_fail'] / n:.4f}" if n else None,
                 "override_rate": f"{overrides / reviewed:.4f}" if reviewed else None,
                 "anchored_rate": f"{k['anchored'] / n:.4f}" if n else None},
        "alerts_open": alerts, "alert_types": alert_types,
        "hourly": [dict(r) for r in hourly], "by_class": [dict(r) for r in by_class],
        "by_line": [dict(r) for r in by_line], "by_model": [dict(r) for r in by_model], "by_risk": risk,
        "anchoring": {**dict(anchor), "last_confirmed": iso(anchor["last_confirmed"]), "queued_events": queued},
    }
