"""RFC 8785 canonicalization with the LEDGEIT 'integers only' restriction (SPEC §1)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

import rfc8785

MAX_SAFE_INT = 2**53 - 1


def _check(value: Any, path: str = "$") -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_INT:
            raise ValueError(f"{path}: integer outside ±2^53-1")
        return
    if isinstance(value, float):
        raise ValueError(f"{path}: floats are not allowed in hashed payloads; use a decimal string")
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError(f"{path}: object keys must be strings")
            _check(v, f"{path}.{k}")
        return
    if isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            _check(v, f"{path}[{i}]")
        return
    raise ValueError(f"{path}: unsupported type {type(value).__name__}")


def canonicalize(value: Any) -> bytes:
    """Return the canonical UTF-8 bytes of ``value``."""
    _check(value)
    return rfc8785.dumps(value)


def fmt_decimal(value: float | Decimal | str, places: int = 4) -> str:
    """Format a number as a fixed-point decimal string (default 4 places, banker's rounding)."""
    q = Decimal(1).scaleb(-places)
    return str(Decimal(str(value)).quantize(q, rounding=ROUND_HALF_EVEN))


def fmt_ts(dt: datetime) -> str:
    """UTC ISO-8601 with milliseconds and Z suffix."""
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))
