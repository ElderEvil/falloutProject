"""Persistent sync-to-async bridge for long-lived Dramatiq worker threads.

The engine and asyncpg pool are bound to the loop that created them, so asyncio.run per
message would force a fresh engine and type introspection every tick. One loop per worker
thread; process-local by design (the web app keeps its own loop/engine).
"""

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any

_thread_local = threading.local()


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run ``coro`` on the calling thread's persistent event loop."""
    loop = getattr(_thread_local, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _thread_local.loop = loop
    return loop.run_until_complete(coro)
