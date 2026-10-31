"""Optional per-vault tick timing instrumentation."""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from hashlib import sha256
from time import perf_counter, time
from typing import TypedDict

from sqlalchemy import Connection, Engine, event
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession


class TickProfileSummary(TypedDict):
    vault_key: str
    dispatch_key: str
    queue_ms: float | None
    total_ms: float
    phases_ms: dict[str, float]


def profile_key(value: str) -> str:
    """Return a stable, non-reversible correlation key for profile grouping."""
    return sha256(value.encode()).hexdigest()[:16]


@dataclass
class TickProfile:
    """Wall-clock phases for one vault tick."""

    vault_key: str
    dispatch_key: str
    enqueued_at: float | None = None
    started_at: float = field(default_factory=time)
    started_perf: float = field(default_factory=perf_counter)
    phases: dict[str, float] = field(default_factory=dict)
    total_ms: float = 0.0

    @property
    def queue_ms(self) -> float | None:
        if self.enqueued_at is None:
            return None
        return max(0.0, (self.started_at - self.enqueued_at) * 1000)

    def add(self, name: str, elapsed_ms: float) -> None:
        self.phases[name] = self.phases.get(name, 0.0) + elapsed_ms

    def finish(self) -> None:
        self.total_ms = (perf_counter() - self.started_perf) * 1000

    def summary(self) -> TickProfileSummary:
        return {
            "vault_key": self.vault_key,
            "dispatch_key": self.dispatch_key,
            "queue_ms": self.queue_ms,
            "total_ms": self.total_ms,
            "phases_ms": {name: round(elapsed, 2) for name, elapsed in self.phases.items()},
        }


_current_profile: ContextVar[TickProfile | None] = ContextVar("tick_profile", default=None)


def set_current_profile(profile: TickProfile | None) -> Token[TickProfile | None]:
    return _current_profile.set(profile)


def reset_current_profile(token: Token[TickProfile | None]) -> None:
    _current_profile.reset(token)


def current_profile() -> TickProfile | None:
    return _current_profile.get()


def _executable_bind(db_session: AsyncSession) -> Connection | Engine | None:
    bind = db_session.get_bind()
    if isinstance(bind, AsyncEngine):
        return bind.sync_engine
    if isinstance(bind, AsyncConnection):
        return bind.sync_connection
    if isinstance(bind, (Connection, Engine)):
        return bind
    return None


@contextmanager
def tick_sql_phase(db_session: AsyncSession, name: str) -> Generator[None]:
    """Record cursor execution time only.

    ``AsyncSession.execute`` may also hydrate ORM rows and run selectin loads;
    this context captures the database cursor time so the caller can attribute
    the remaining execute wall time separately.
    """
    profile = _current_profile.get()
    bind = _executable_bind(db_session) if profile is not None else None
    if profile is None or bind is None:
        yield
        return

    starts: list[float] = []

    def before_cursor_execute(*_args: object) -> None:
        starts.append(perf_counter())

    def after_cursor_execute(*_args: object) -> None:
        if starts:
            profile.add(f"{name}.sql", (perf_counter() - starts.pop()) * 1000)

    event.listen(bind, "before_cursor_execute", before_cursor_execute)
    event.listen(bind, "after_cursor_execute", after_cursor_execute)
    try:
        yield
    finally:
        event.remove(bind, "before_cursor_execute", before_cursor_execute)
        event.remove(bind, "after_cursor_execute", after_cursor_execute)


@contextmanager
def tick_phase(name: str) -> Generator[None]:
    """Record a named phase when profiling is active; otherwise do nothing."""
    profile = _current_profile.get()
    if profile is None:
        yield
        return

    started = perf_counter()
    try:
        yield
    finally:
        profile.add(name, (perf_counter() - started) * 1000)
