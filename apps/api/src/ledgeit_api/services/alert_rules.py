"""Periodic alert rules (run by the anchor worker every ~30 s)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import Connection, text

from ..core.yamlconf import risk_config
from .alerts import raise_alert


def _open_with(conn: Connection, alert_type: str, key: str, value: str) -> bool:
    return conn.execute(text(
        "SELECT 1 FROM alerts WHERE alert_type=CAST(:t AS alert_t) AND status<>'RESOLVED' AND details->>:k = :v"
    ), {"t": alert_type, "k": key, "v": value}).first() is not None


def delayed_approvals(conn: Connection, now: datetime) -> int:
    mins = int(risk_config()["alerts"]["delayed_approval_minutes"])
    rows = conn.execute(text(
        "SELECT o.id::text, o.inspection_id::text, o.created_at, u.employee_code FROM overrides o "
        "JOIN users u ON u.id=o.operator_id LEFT JOIN override_approvals a ON a.override_id=o.id "
        "WHERE a.id IS NULL AND o.created_at < :t"
    ), {"t": now - timedelta(minutes=mins)}).mappings().all()
    n = 0
    for r in rows:
        if not _open_with(conn, "DELAYED_APPROVAL", "override_id", r["id"]):
            raise_alert(conn, "DELAYED_APPROVAL", "MEDIUM", {"override_id": r["id"], "operator": r["employee_code"],
                                                             "waiting_minutes": mins}, r["inspection_id"])
            n += 1
    return n


def high_override_rate(conn: Connection) -> int:
    cfg = risk_config()["alerts"]["high_override_rate"]
    window, threshold = int(cfg["window"]), Decimal(cfg["threshold"])
    models = conn.execute(text("SELECT id::text, name, version FROM ai_models")).mappings().all()
    n = 0
    for m in models:
        row = conn.execute(text("""
            SELECT count(*) AS reviewed, count(*) FILTER (WHERE overridden) AS overridden FROM (
              SELECT i.id, EXISTS (SELECT 1 FROM overrides o WHERE o.inspection_id=i.id) AS overridden
              FROM inspections i JOIN inspection_status s ON s.inspection_id=i.id
              WHERE i.model_id=:m AND s.status NOT IN ('PENDING_REVIEW','AUTO_ACCEPTED')
              ORDER BY i.inspected_at DESC LIMIT :w) x
        """), {"m": m["id"], "w": window}).mappings().one()
        if row["reviewed"] < min(window, 10):
            continue
        rate = Decimal(row["overridden"]) / Decimal(row["reviewed"])
        label = f"{m['name']}@{m['version']}"
        if rate > threshold and not _open_with(conn, "HIGH_OVERRIDE_RATE", "model", label):
            raise_alert(conn, "HIGH_OVERRIDE_RATE", "MEDIUM", {
                "model": label, "rate": f"{rate:.4f}", "threshold": str(threshold),
                "overridden": row["overridden"], "reviewed": row["reviewed"]})
            n += 1
    return n


def missing_anchors(conn: Connection, now: datetime) -> int:
    mins = int(risk_config()["alerts"]["missing_anchor_minutes"])
    rows = conn.execute(text(
        "SELECT id, merkle_root, status::text AS status FROM anchor_batches "
        "WHERE status IN ('PENDING','SUBMITTED') AND created_at < :t"
    ), {"t": now - timedelta(minutes=mins)}).mappings().all()
    n = 0
    for r in rows:
        if not _open_with(conn, "MISSING_ANCHOR", "batch_id", str(r["id"])):
            raise_alert(conn, "MISSING_ANCHOR", "HIGH", {"batch_id": str(r["id"]), "merkle_root": r["merkle_root"],
                                                         "reason": f"not confirmed after {mins} min"})
            n += 1
    return n


def run_rules(conn: Connection, now: datetime) -> dict:
    return {"delayed_approval": delayed_approvals(conn, now), "high_override_rate": high_override_rate(conn),
            "missing_anchor": missing_anchors(conn, now)}
