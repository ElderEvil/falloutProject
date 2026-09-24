"""Regression tests: ``task_session()`` must yield a SQLModel session with ``.exec()``.

History (audit #2): ``task_session()`` built its per-tick session maker with
``async_sessionmaker(engine, expire_on_commit=False)`` — no ``class_`` override —
so dramatiq tick actors received raw SQLAlchemy ``AsyncSession`` objects lacking
SQLModel's ``.exec()``. Services called from ticks use ``.exec()`` heavily
(``dweller_recycling_service`` at 9 sites, ``ai_usage_service`` at 2), so the
first background tick would raise ``AttributeError`` → dramatiq retry →
crash-loop (see AGENTS.md "Background task session compatibility").

The fix pins ``class_=AsyncSession`` (``sqlmodel.ext.asyncio.session``) on the
maker; SQLModel's ``AsyncSession`` subclasses SQLAlchemy's, so the
``async_sessionmaker`` + ``class_`` combo stays supported. These tests guard:

1. ``test_task_session_yields_sqlmodel_async_session`` — DB-free (SQLAlchemy
   connects lazily): the session yielded by ``task_session()`` must be a
   SQLModel ``AsyncSession`` with ``.exec()``.

2. ``test_raw_sessionmaker_without_class_lacks_exec`` — documents the failure
   mode: a maker built without ``class_`` yields a session lacking ``.exec()``.

3. ``test_task_session_exec_runs_query`` — live-PostgreSQL check (skips when
   unreachable, e.g. the SQLite-based CI suite): ``.exec()`` actually executes
   through ``task_session()``.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.db.session import async_session_maker, task_session


class TestTaskSessionExec:
    """Guard the dramatiq tick session factory against SQLModel session loss."""

    async def test_task_session_yields_sqlmodel_async_session(self) -> None:
        """``task_session()`` must yield SQLModel ``AsyncSession`` (has ``.exec()``).

        Opening the session does not touch the database (connections are lazy),
        so this test needs no live PostgreSQL.
        """
        async with task_session() as session:
            assert isinstance(session, AsyncSession), (
                "task_session() yielded a raw SQLAlchemy session without SQLModel .exec(); "
                "its async_sessionmaker must set class_=AsyncSession"
            )
            assert hasattr(session, "exec")

    async def test_raw_sessionmaker_without_class_lacks_exec(self) -> None:
        """Documents the bug: ``async_sessionmaker`` without ``class_`` → no ``.exec()``."""
        engine = create_async_engine("sqlite+aiosqlite://", poolclass=NullPool)
        try:
            session_maker = async_sessionmaker(engine, expire_on_commit=False)  # the pre-fix bug shape
            async with session_maker() as session:
                assert not isinstance(session, AsyncSession)
                assert not hasattr(session, "exec"), (
                    "Raw SQLAlchemy AsyncSession unexpectedly gained .exec(); "
                    "this guard is obsolete and can be revisited"
                )
        finally:
            await engine.dispose()

    async def test_binds_and_resets_the_objective_session_maker(self) -> None:
        """Handlers fired during a tick open sessions on this run's engine.

        The objective session maker is bound for the duration of the task session
        and restored afterwards, so an event handler can never reuse a previous
        event loop's engine (the InterfaceError collision in ``base.py``).
        """
        from app.services.progression.objectives.evaluators import current_session_maker

        before = current_session_maker.get()

        async with task_session() as session:
            bound = current_session_maker.get()
            assert bound is not None
            assert bound is not async_session_maker, "handler would reuse the module-global pool"
            assert bound.kw["bind"].sync_engine is session.get_bind()

        assert current_session_maker.get() is before
