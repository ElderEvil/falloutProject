"""Optional per-vault tick timing instrumentation."""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from time import perf_counter, time
from typing import TypedDict


class TickProfileSummary(TypedDict):
    queue_ms: float | None
    total_ms: float
    phases_ms: dict[str, float]


@dataclass
class TickProfile:
    """Wall-clock phases for one vault tick."""

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
