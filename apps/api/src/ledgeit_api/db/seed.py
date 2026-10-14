"""Idempotent demo seed: plant, lines, devices, products, batches, users.

Device private keys are written to services/edge-simulator/keys/<DEVICE>.json (git-ignored)
and only the public keys are stored in the DB.

Usage: python -m ledgeit_api.db.seed
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Connection, text

from ledgeit_proof import generate_keypair, genesis_hash

from ..core.config import REPO_ROOT
from ..core.security import hash_password
from .engine import get_engine

KEYS_DIR = REPO_ROOT / "services" / "edge-simulator" / "keys"
DEMO_PASSWORD = "ledgeit123"

USERS = [
    ("OP-0001", "Rohan Operator", "operator@ledgeit.dev", "OPERATOR"),
    ("QE-0042", "Priya Engineer", "qe@ledgeit.dev", "QUALITY_ENGINEER"),
    ("QE-0043", "Arjun Engineer", "qe2@ledgeit.dev", "QUALITY_ENGINEER"),
    ("QM-0007", "Meera Manager", "qm@ledgeit.dev", "QUALITY_MANAGER"),
    ("AUD-0003", "Vikram Auditor", "auditor@ledgeit.dev", "AUDITOR"),
    ("ADM-0001", "Admin", "admin@ledgeit.dev", "ADMIN"),
]
LINES = [("LINE-A", "Hot-rolled strip line A"), ("LINE-B", "Cold-rolled sheet line B")]
DEVICES = [("CAM-A-01", "LINE-A"), ("CAM-B-01", "LINE-B")]
PRODUCTS = [("STEEL-HR-2MM", "Hot-rolled steel strip 2 mm", False),
            ("STEEL-AUTO-PNL", "Automotive body panel steel (regulated)", True)]
BATCHES = [("BATCH-A-001", "STEEL-HR-2MM", "LINE-A"), ("BATCH-B-001", "STEEL-AUTO-PNL", "LINE-B")]


def device_key(device_code: str, keys_dir: Path = KEYS_DIR) -> dict:
    """Load or create a device keypair file."""
    keys_dir.mkdir(parents=True, exist_ok=True)
    f = keys_dir / f"{device_code}.json"
    if f.exists():
        return json.loads(f.read_text())
    kp = generate_keypair()
    data = {"device_code": device_code, "seed_b64": kp.seed_b64, "public_key_b64": kp.public_key_b64}
    f.write_text(json.dumps(data, indent=2))
    f.chmod(0o600)
    return data


def ensure_line(conn: Connection, code: str, name: str, plant_id: str) -> str:
    lid = conn.execute(text("SELECT id::text FROM production_lines WHERE code=:c"), {"c": code}).scalar()
    if lid:
        return lid
    lid = conn.execute(text(
        "INSERT INTO production_lines(plant_id, code, name, genesis_hash) VALUES (:p, :c, :n, :g) RETURNING id::text"
    ), {"p": plant_id, "c": code, "n": name, "g": genesis_hash(code)}).scalar_one()
    conn.execute(text("INSERT INTO line_heads(line_id, last_seq, last_event_hash) VALUES (:l, 0, :g)"),
                 {"l": lid, "g": genesis_hash(code)})
    return lid


def ensure_device(conn: Connection, code: str, line_id: str, public_key: str) -> str:
    did = conn.execute(text("SELECT id::text FROM devices WHERE device_code=:c"), {"c": code}).scalar()
    if did:
        conn.execute(text("UPDATE devices SET public_key=:k WHERE id=:id"), {"k": public_key, "id": did})
        return did
    return conn.execute(text(
        "INSERT INTO devices(line_id, device_code, public_key) VALUES (:l, :c, :k) RETURNING id::text"
    ), {"l": line_id, "c": code, "k": public_key}).scalar_one()


def seed(conn: Connection, keys_dir: Path = KEYS_DIR) -> dict:
    plant_id = conn.execute(text("SELECT id::text FROM plants WHERE name='Pune Works'")).scalar()
    if not plant_id:
        plant_id = conn.execute(text(
            "INSERT INTO plants(name, location) VALUES ('Pune Works', 'Pune, Maharashtra') RETURNING id::text"
        )).scalar_one()
    line_ids = {code: ensure_line(conn, code, name, plant_id) for code, name in LINES}
    for code, line in DEVICES:
        ensure_device(conn, code, line_ids[line], device_key(code, keys_dir)["public_key_b64"])
    for sku, name, reg in PRODUCTS:
        conn.execute(text(
            "INSERT INTO products(sku, name, is_regulated) VALUES (:s, :n, :r) ON CONFLICT (sku) DO NOTHING"
        ), {"s": sku, "n": name, "r": reg})
    for bcode, sku, line in BATCHES:
        conn.execute(text(
            "INSERT INTO batches(batch_code, product_id, line_id, started_at) "
            "SELECT :b, p.id, :l, :t FROM products p WHERE p.sku=:s ON CONFLICT (batch_code) DO NOTHING"
        ), {"b": bcode, "s": sku, "l": line_ids[line], "t": datetime.now(timezone.utc)})
    pw = hash_password(DEMO_PASSWORD)
    for ecode, name, email, role in USERS:
        conn.execute(text(
            "INSERT INTO users(employee_code, full_name, email, password_hash, role) "
            "VALUES (:c, :n, :e, :p, CAST(:r AS user_role)) ON CONFLICT (employee_code) DO NOTHING"
        ), {"c": ecode, "n": name, "e": email, "p": pw, "r": role})
    return {"plant_id": plant_id, "lines": line_ids}


def main() -> None:
    with get_engine().begin() as conn:
        out = seed(conn)
    print(f"seeded plant {out['plant_id']} lines {list(out['lines'])}; demo password: {DEMO_PASSWORD}")
    for _, _, email, role in USERS:
        print(f"  {role:<17} {email}")


if __name__ == "__main__":
    main()
