"""Anchor worker process: `python -m ledgeit_api.anchoring.run` (also services/anchor-worker)."""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone

from ..chain.client import ensure_local_deployment, get_chain
from ..core.config import get_settings
from ..db.engine import get_engine
from ..services.alert_rules import run_rules
from .worker import tick

log = logging.getLogger("ledgeit.anchor")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="LEDGEIT anchor worker")
    ap.add_argument("--interval", type=float, default=1.0, help="seconds between ticks")
    ap.add_argument("--rules-every", type=float, default=30.0, help="seconds between alert-rule runs")
    ap.add_argument("--once", action="store_true", help="run one tick and exit")
    ap.add_argument("--flush", action="store_true", help="with --once: anchor everything pending now")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    s = get_settings()
    if s.chain == "local":
        addr = ensure_local_deployment()
        log.info("CHAIN=local, LedgeitAnchor at %s", addr)
    chain = get_chain()
    if chain is None:
        log.warning("CHAIN=%s with no contract: batches will be built but not submitted", s.chain)
    else:
        log.info("anchoring to %s (chain id %s) contract %s", chain.network, chain.chain_id, chain.contract_address)
    engine = get_engine()
    last_rules = 0.0
    while True:
        out = tick(engine, chain, force=a.flush)
        if out["created"] or out["confirmed"]:
            log.info("tick: %s", out)
        if time.monotonic() - last_rules >= a.rules_every:
            with engine.begin() as conn:
                r = run_rules(conn, datetime.now(timezone.utc))
            if any(r.values()):
                log.info("alert rules: %s", r)
            last_rules = time.monotonic()
        if a.once:
            return 0
        time.sleep(a.interval)


if __name__ == "__main__":
    raise SystemExit(main())
