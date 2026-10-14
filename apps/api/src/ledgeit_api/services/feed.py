"""In-process pub/sub for the live WebSocket feed (ADR-008: no Redis needed for one API process)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import threading
from typing import Any


class FeedHub:
    def __init__(self) -> None:
        self._subs: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        with self._lock:
            self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._subs.discard(q)

    def publish(self, kind: str, data: dict[str, Any]) -> None:
        """Thread-safe; callable from sync request handlers."""
        if not self._loop:
            return
        msg = json.dumps({"type": kind, "data": data}, default=str)
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            self._loop.call_soon_threadsafe(_offer, q, msg)


def _offer(q: asyncio.Queue, msg: str) -> None:
    if q.full():
        with contextlib.suppress(asyncio.QueueEmpty):
            q.get_nowait()  # drop oldest for slow clients
    q.put_nowait(msg)


hub = FeedHub()
