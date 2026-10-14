from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, text

from ..db.json import jdump


def raise_alert(conn: Connection, alert_type: str, severity: str, details: dict[str, Any],
                inspection_id: str | None = None, dedupe: bool = False) -> str | None:
    """Insert an alert. With dedupe=True, skip if an OPEN alert of the same type exists for this inspection."""
    if dedupe and inspection_id:
        exists = conn.execute(text(
            "SELECT 1 FROM alerts WHERE alert_type=CAST(:t AS alert_t) AND inspection_id=:i AND status='OPEN'"
        ), {"t": alert_type, "i": inspection_id}).first()
        if exists:
            return None
    return conn.execute(text(
        "INSERT INTO alerts(alert_type, severity, inspection_id, details) "
        "VALUES (CAST(:t AS alert_t), CAST(:s AS risk_t), :i, CAST(:d AS jsonb)) RETURNING id::text"
    ), {"t": alert_type, "s": severity, "i": inspection_id, "d": jdump(details)}).scalar_one()
