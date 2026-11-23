import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.async_runtime import run_async
from app.db.session import async_session_maker, task_session, task_session_maker


class TestTaskSessionExec:
    async def test_task_session_yields_sqlmodel_async_session(self) -> None:
        # Opening the session does not touch the database (connections are lazy).
        async with task_session() as session:
            assert isinstance(session, AsyncSession), (
                "task_session() yielded a raw SQLAlchemy session without SQLModel .exec(); "
                "its async_sessionmaker must set class_=AsyncSession"
            )
            assert hasattr(session, "exec")

    async def test_task_session_maker_yields_sqlmodel_sessions(self) -> None:
        async with task_session_maker() as session_maker, session_maker() as session:
            assert isinstance(session, AsyncSession)
            assert hasattr(session, "exec")

    async def test_task_session_reuses_the_loop_engine(self) -> None:
        async with task_session() as first, task_session() as second:
            assert first.get_bind() is second.get_bind()

    def test_run_async_reuses_the_thread_loop(self) -> None:
        async def loop_id() -> int:
            return id(asyncio.get_running_loop())

        assert run_async(loop_id()) == run_async(loop_id())

    async def test_raw_sessionmaker_without_class_lacks_exec(self) -> None:
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
        from app.services.progression.objectives.evaluators import current_session_maker

        before = current_session_maker.get()
        async with task_session() as session:
            bound = current_session_maker.get()
            assert bound is not None
            assert bound is not async_session_maker, "handler would reuse the module-global pool"
            assert bound.kw["bind"].sync_engine is session.get_bind()
        assert current_session_maker.get() is before
