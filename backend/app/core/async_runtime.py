"""Persistent synchronous-to-async bridge for long-lived Dramatiq worker threads.

Dramatiq actor functions are synchronous and default to ``asyncio.run``, which
creates and closes a new event loop for every message. The database engine and
its asyncpg pool are bound to the loop that created them, so a fresh loop also
forces a fresh engine, connection setup and type introspection on every tick.

Worker threads are long-lived, so keep one loop per thread and run each actor
coroutine on it. This is process-local by design; the web app keeps using its
own loop and engine.
"""

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

_T = TypeVar("_T")

_thread_local = threading.local()


def run_async(coro: Coroutine[Any, Any, _T]) -> _T:
    """Run ``coro`` on the calling thread's persistent event loop."""
    loop = getattr(_thread_local, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _thread_local.loop = loop
    return loop.run_until_complete(coro)
