from __future__ import annotations

from datetime import datetime, timezone

from ledgeit_proof import fmt_ts, parse_ts


def now_ms() -> datetime:
    """Current UTC time truncated to milliseconds (so it round-trips through fmt_ts exactly)."""
    n = datetime.now(timezone.utc)
    return n.replace(microsecond=(n.microsecond // 1000) * 1000)


def iso(dt: datetime | None) -> str | None:
    return fmt_ts(dt) if dt else None


__all__ = ["fmt_ts", "iso", "now_ms", "parse_ts"]
