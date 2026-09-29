"""In-process event bus feeding the SSE stream (/api/events).

publish() is safe to call from sync route handlers (they run in a threadpool):
each subscriber queue is fed via its own event loop's call_soon_threadsafe.
Recent events are kept so a UI that reconnects (or polls) can catch up.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import deque
from typing import Any

_lock = threading.Lock()
_subscribers: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []
_recent: deque[dict[str, Any]] = deque(maxlen=100)
_seq = 0


def publish(event: str, data: dict[str, Any]) -> None:
    global _seq
    with _lock:
        _seq += 1
        msg = {"id": _seq, "event": event, "data": data, "ts": time.time()}
        _recent.append(msg)
        subscribers = list(_subscribers)
    for loop, queue in subscribers:
        try:
            loop.call_soon_threadsafe(queue.put_nowait, msg)
        except RuntimeError:  # loop closed; the SSE handler will unsubscribe
            pass


def subscribe() -> tuple[asyncio.AbstractEventLoop, asyncio.Queue]:
    sub = (asyncio.get_running_loop(), asyncio.Queue())
    with _lock:
        _subscribers.append(sub)
    return sub


def unsubscribe(sub: tuple[asyncio.AbstractEventLoop, asyncio.Queue]) -> None:
    with _lock:
        if sub in _subscribers:
            _subscribers.remove(sub)


def recent(since_id: int = 0) -> list[dict[str, Any]]:
    with _lock:
        return [m for m in _recent if m["id"] > since_id]


def clear() -> None:
    with _lock:
        _recent.clear()


def format_sse(msg: dict[str, Any]) -> str:
    return f"id: {msg['id']}\nevent: {msg['event']}\ndata: {json.dumps(msg['data'], default=str)}\n\n"
