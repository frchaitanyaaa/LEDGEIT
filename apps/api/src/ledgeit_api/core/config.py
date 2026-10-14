from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(os.environ.get("LEDGEIT_ROOT", Path(__file__).resolve().parents[5]))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ledgeit:ledgeit@localhost:5432/ledgeit"
    tamper_database_url: str | None = None

    jwt_secret: str = "change-me-in-production"
    jwt_access_minutes: int = 60
    jwt_refresh_days: int = 7

    storage_backend: str = "local"  # local | s3
    storage_dir: str = str(REPO_ROOT / "var" / "evidence")
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "ledgeit"
    s3_secret_key: str = "ledgeit123"
    s3_bucket: str = "evidence"

    chain: str = "local"  # local | amoy | none
    rpc_url_local: str = "http://localhost:8545"
    rpc_url_amoy: str = "https://rpc-amoy.polygon.technology"
    anchor_private_key: str = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
    contract_address: str = ""
    public_rpc_url: str = ""  # RPC the browser uses for in-browser verification

    risk_config: str = str(REPO_ROOT / "config" / "risk.yaml")
    economics_config: str = str(REPO_ROOT / "config" / "economics.yaml")

    public_base_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    signed_at_skew_seconds: int = 600

    @property
    def deployments_dir(self) -> Path:
        return REPO_ROOT / "contracts" / "deployments"


@lru_cache
def get_settings() -> Settings:
    return Settings()
