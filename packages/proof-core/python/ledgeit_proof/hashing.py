from __future__ import annotations

import hashlib
from typing import Any

from .canonical import canonicalize


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_json(value: Any) -> str:
    return sha256_hex(canonicalize(value))
