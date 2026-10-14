"""Replay detection (CHAITANYA.md §5.8): exact SHA-256 duplicates and near-duplicates by pHash."""

from __future__ import annotations

import io
from datetime import datetime, timedelta

import imagehash
from PIL import Image
from sqlalchemy import Connection, text

from ..core.yamlconf import risk_config


def compute_phash(data: bytes) -> str:
    return str(imagehash.phash(Image.open(io.BytesIO(data))))


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def find_replays(conn: Connection, sha256: str, phash: str, unit_serial: str, now: datetime) -> dict:
    """Returns {"exact": [...], "near": [...]} matches against earlier IMAGE evidence."""
    cfg = risk_config()["replay"]
    exact = conn.execute(text(
        "SELECT i.inspection_code, i.unit_serial FROM evidence e JOIN inspections i ON i.evidence_id=e.id "
        "WHERE e.sha256=:h AND e.kind='IMAGE' AND i.unit_serial<>:u LIMIT 5"
    ), {"h": sha256, "u": unit_serial}).mappings().all()
    since = now - timedelta(days=int(cfg["lookback_days"]))
    rows = conn.execute(text(
        "SELECT e.phash, e.sha256, i.inspection_code, i.unit_serial FROM evidence e "
        "JOIN inspections i ON i.evidence_id=e.id WHERE e.kind='IMAGE' AND e.captured_at>=:t AND e.sha256<>:h "
        "AND e.phash IS NOT NULL"
    ), {"t": since, "h": sha256}).mappings().all()
    maxd = int(cfg["phash_max_distance"])
    near = []
    for r in rows:
        d = hamming(phash, r["phash"])
        if d <= maxd and r["unit_serial"] != unit_serial:
            near.append({"inspection_code": r["inspection_code"], "unit_serial": r["unit_serial"], "distance": d})
    near.sort(key=lambda x: x["distance"])
    return {"exact": [dict(e) for e in exact], "near": near[:5]}
