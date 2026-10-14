"""Test harness: a dedicated database (TEST_DATABASE_URL), migrated once, reset before each test."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

TEST_URL = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get("DATABASE_URL", "postgresql+psycopg://ledgeit:ledgeit@localhost:5432/ledgeit").rsplit("/", 1)[0]
    + "/ledgeit_test",
)
os.environ["DATABASE_URL"] = TEST_URL
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("CHAIN", "none")
os.environ.setdefault("JWT_SECRET", "test-secret")


def _recreate_db(url: str) -> None:
    u = make_url(url)
    admin = create_engine(u.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:d AND pid<>pg_backend_pid()"),
                  {"d": u.database})
        c.execute(text(f'DROP DATABASE IF EXISTS "{u.database}"'))
        c.execute(text(f'CREATE DATABASE "{u.database}"'))
    admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def _database(tmp_path_factory):
    os.environ["STORAGE_DIR"] = str(tmp_path_factory.mktemp("evidence"))
    _recreate_db(TEST_URL)
    from ledgeit_api.core.config import get_settings
    from ledgeit_api.db.migrate import migrate

    get_settings.cache_clear()
    migrate(TEST_URL, verbose=False)
    yield


PROOF_AND_DATA_TABLES = [
    "verifications", "alerts", "reports", "cost_entries", "inspection_status", "blockchain_txs", "anchor_items",
    "anchor_queue", "anchor_batches", "override_approvals", "overrides", "inspection_events", "inspections",
    "evidence", "ai_models", "batches", "products", "devices", "line_heads", "production_lines", "plants",
    "user_keys", "users",
]


@pytest.fixture
def engine():
    from ledgeit_api.db.engine import get_engine

    return get_engine()


@pytest.fixture(autouse=True)
def _reset(engine, tmp_path):
    # Superuser + replica mode skips the append-only triggers (exactly what the Tamper Lab abuses).
    with engine.begin() as c:
        c.execute(text("SET LOCAL session_replication_role = replica"))
        c.execute(text("TRUNCATE " + ", ".join(PROOF_AND_DATA_TABLES) + " CASCADE"))
    yield


@pytest.fixture
def keys_dir(tmp_path) -> Path:
    return tmp_path / "keys"


@pytest.fixture
def seeded(engine, keys_dir):
    from ledgeit_api.db.seed import seed

    with engine.begin() as c:
        return seed(c, keys_dir)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from ledgeit_api.main import create_app

    with TestClient(create_app()) as c:
        yield c


def login(client, email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "ledgeit123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client, seeded):
    def _auth(role: str = "qe") -> dict:
        return login(client, f"{role}@ledgeit.dev")

    return _auth


# ---------------- end-to-end helpers: in-process AI inspector + edge device ----------------
import sys  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "services" / "ai-inspector"))


@pytest.fixture(scope="session")
def ai_client():
    from fastapi.testclient import TestClient

    from app.main import app as ai_app  # services/ai-inspector

    return TestClient(ai_app)


@pytest.fixture
def make_device(client, ai_client, seeded, keys_dir):
    import json as _json

    from simulator.device import EdgeDevice, http_infer

    def _make(code: str = "CAM-A-01") -> EdgeDevice:
        key = _json.loads((keys_dir / f"{code}.json").read_text())
        d = EdgeDevice(code=code, seed_b64=key["seed_b64"], api=client, infer=http_infer(ai_client))
        d.sync_head()
        return d

    return _make


@pytest.fixture
def frame():
    from simulator.synth import generate

    def _frame(i: int, defect_rate: float = 0.35) -> tuple[bytes, str | None]:
        s = generate(i, defect_rate=defect_rate)
        return s.jpeg, s.truth

    return _frame
