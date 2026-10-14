"""DEV ONLY: drop and recreate the LEDGEIT database, migrate, seed. Refuses unless the DB host is local."""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from ledgeit_api.core.config import get_settings
from ledgeit_api.db.migrate import migrate


def main() -> int:
    url = make_url(get_settings().database_url)
    if url.host not in ("localhost", "127.0.0.1", "postgres"):
        print(f"refusing to reset non-local database host {url.host}")
        return 2
    if "--yes" not in sys.argv and input(f"Drop database {url.database} on {url.host}? [y/N] ").lower() != "y":
        return 1
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:d AND pid<>pg_backend_pid()"),
                  {"d": url.database})
        c.execute(text(f'DROP DATABASE IF EXISTS "{url.database}"'))
        c.execute(text(f'CREATE DATABASE "{url.database}"'))
    migrate()
    from ledgeit_api.db.seed import main as seed_main

    seed_main()
    print("NOTE: the local chain still holds old roots; restart the hardhat node too for a clean slate "
          "(and delete contracts/deployments/localhost.json).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
