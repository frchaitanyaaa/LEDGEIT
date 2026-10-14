from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Connection, Engine, create_engine

from ..core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=10, max_overflow=20)


def get_conn() -> Iterator[Connection]:
    """FastAPI dependency: one transaction per request, committed on success."""
    with get_engine().begin() as conn:
        yield conn
