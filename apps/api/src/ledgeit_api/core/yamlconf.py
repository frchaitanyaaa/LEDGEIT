"""YAML config files that reload when they change on disk (risk thresholds are tuned live in the demo)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import yaml

from .config import get_settings

_cache: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()


def load_yaml(path: str | Path) -> Any:
    p = Path(path)
    mtime = p.stat().st_mtime
    with _lock:
        hit = _cache.get(str(p))
        if hit and hit[0] == mtime:
            return hit[1]
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        _cache[str(p)] = (mtime, data)
        return data


def risk_config() -> dict:
    return load_yaml(get_settings().risk_config)


def economics_config() -> dict:
    return load_yaml(get_settings().economics_config)
