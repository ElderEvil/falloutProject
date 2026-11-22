import asyncio
from typing import Annotated
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import DBSession
from app.core.config import settings
from app.db.session import get_async_session


@pytest.mark.parametrize("exit_mode", ["success", "exception", "cancel"])
@pytest.mark.parametrize("database", ["sqlite", pytest.param("postgresql", marks=pytest.mark.integration)])
async def test_shared_session_cap_queues_across_routes_and_releases_after_cleanup(tmp_path, exit_mode, database):
    limit = settings.API_DB_SESSION_CONCURRENCY
    application_name = f"concurrency-test-{uuid4()}"
    uri = str(settings.ASYNC_DATABASE_URI) if database == "postgresql" else f"sqlite+aiosqlite:///{tmp_path}/cap.db"
    engine = create_async_engine(
        uri,
        pool_size=limit + 2,
        max_overflow=0,
        connect_args={"server_settings": {"application_name": application_name}} if database == "postgresql" else {},
    )
    if database == "postgresql":
        try:
            async with engine.connect():
                pass
        except Exception:
            await engine.dispose()
            pytest.skip("requires a reachable PostgreSQL server")

    async def idle_transactions():
        async with engine.connect() as connection:
            return (
                await connection.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE application_name = :name AND state = 'idle in transaction'"
                    ),
                    {"name": application_name},
                )
            ).scalar_one()

    if database == "postgresql":
        assert await idle_transactions() == 0
    maker = async_sessionmaker(engine, class_=AsyncSession)
    app = FastAPI()
    entered = asyncio.Queue()
    release = asyncio.Event()
    cleanup_started = asyncio.Event()
    finish_cleanup = asyncio.Event()
    opened = 0

    async def sessions():
        nonlocal opened
        opened += 1
        async with maker() as session:
            try:
                yield session
            finally:
                cleanup_started.set()
                await finish_cleanup.wait()

    app.dependency_overrides[get_async_session] = sessions

    async def nested(session: DBSession):
        return session

    @app.get("/a/{number}")
    @app.get("/b/{number}")
    async def hold(number: int, session: DBSession, cached: Annotated[AsyncSession, Depends(nested)]):
        assert session is cached
        assert (await session.execute(text("SELECT 1"))).scalar_one() == 1
        entered.put_nowait(number)
        await release.wait()
        if exit_mode == "exception":
            raise HTTPException(409, "rejected")
        return number

    tasks = []
    try:
        async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
            tasks = [asyncio.create_task(client.get(f"/a/{i}")) for i in range(limit)]
            for _ in range(limit):
                await asyncio.wait_for(entered.get(), 5)
            queued = asyncio.create_task(client.get("/b/100"))
            tasks.append(queued)
            # Let the ASGI task reach the dependency semaphore before checking admission.
            await asyncio.sleep(0.05)
            assert opened == limit
            assert entered.empty()
            assert engine.pool.checkedout() == limit
            if database == "postgresql":
                assert await idle_transactions() == limit

            # A cancelled waiter must neither open a session nor consume a permit.
            queued.cancel()
            with pytest.raises(asyncio.CancelledError):
                await queued
            queued = asyncio.create_task(client.get("/b/101"))
            tasks.append(queued)
            if exit_mode == "cancel":
                tasks[0].cancel()
            else:
                release.set()
            await asyncio.wait_for(cleanup_started.wait(), 5)
            assert opened == limit  # The permit remains held during generator cleanup.
            finish_cleanup.set()
            assert await asyncio.wait_for(entered.get(), 5) == 101
            release.set()
            results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 5)
            responses = [result for result in results if not isinstance(result, BaseException)]
            assert all(
                isinstance(result, asyncio.CancelledError) for result in results if isinstance(result, BaseException)
            )
            assert len(responses) == limit + (exit_mode != "cancel")
            assert all(response.status_code == (409 if exit_mode == "exception" else 200) for response in responses)
            assert opened == limit + 1
            assert engine.pool.checkedout() == 0
            if database == "postgresql":
                assert await idle_transactions() == 0
    finally:
        finish_cleanup.set()
        release.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await engine.dispose()


@pytest.mark.parametrize(
    "path", ["notifications", "game/{vault_id}/ticks", "exploration/{vault_id}", "incidents/{vault_id}"]
)
async def test_open_streams_do_not_consume_api_permits_or_hold_sessions(
    path, user_with_vault, async_session, monkeypatch
):
    from app.api.v1.endpoints import stream
    from app.core.security import create_access_token

    user, vault = user_with_vault
    app = FastAPI()
    app.include_router(stream.router)
    subscribed = asyncio.Queue()
    finish = asyncio.Event()
    opened = 0
    active = 0
    maker = async_sessionmaker(
        async_session.bind, class_=AsyncSession, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    sessions_used = []

    async def sessions():
        nonlocal opened, active
        opened += 1
        active += 1
        async with maker() as session:
            sessions_used.append(session)
            try:
                yield session
            finally:
                active -= 1

    async def subscribe(*_args):
        subscribed.put_nowait(None)
        yield {"event_id": "test", "data": {}}
        await finish.wait()

    app.dependency_overrides[get_async_session] = sessions
    monkeypatch.setattr(stream.sse_manager, "subscribe", subscribe)

    @app.get("/probe")
    async def probe(session: DBSession):
        return (await session.execute(text("SELECT 1"))).scalar_one()

    tasks = []
    try:
        async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}
            url = "/stream/" + path.format(vault_id=vault.id)
            for _ in range(settings.API_DB_SESSION_CONCURRENCY + 1):
                task = asyncio.create_task(client.get(url, headers=headers))
                tasks.append(task)
                await asyncio.wait_for(subscribed.get(), 5)
                assert not task.done()
                assert not sessions_used[-1].in_transaction()
            # Auth, access and endpoint must share exactly one uncapped session per stream.
            assert opened == len(tasks)
            response = await asyncio.wait_for(client.get("/probe"), 5)
            assert response.status_code == 200
            assert response.json() == 1
            finish.set()
            responses = await asyncio.wait_for(asyncio.gather(*tasks), 5)
            assert all(response.status_code == 200 for response in responses)
            assert active == 0
    finally:
        finish.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.parametrize("case", ["invalid_token", "inactive", "foreign_vault"])
@pytest.mark.parametrize("path", ["game/{vault_id}/ticks", "exploration/{vault_id}", "incidents/{vault_id}"])
async def test_stream_access_rejections_are_preserved(
    case, path, async_client, async_session, user_with_vault, superuser
):
    from app.core.security import create_access_token

    user, vault = user_with_vault
    if case == "inactive":
        user.is_active = False
        async_session.add(user)
    elif case == "foreign_vault":
        vault.user_id = superuser.id
        async_session.add(vault)
    await async_session.commit()
    token = "invalid" if case == "invalid_token" else create_access_token(user.id)
    response = await async_client.get(
        "/stream/" + path.format(vault_id=vault.id),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == (401 if case == "invalid_token" else 403)


@pytest.mark.parametrize("case", ["invalid_token", "inactive"])
async def test_notification_stream_preserves_current_user_policy(
    case, async_client, async_session, user_with_vault, monkeypatch
):
    from app.api.v1.endpoints import stream
    from app.core.security import create_access_token

    user, _vault = user_with_vault
    user.is_active = False
    async_session.add(user)
    await async_session.commit()

    async def subscribe(*_args):
        yield {"event_id": "test", "data": {}}

    monkeypatch.setattr(stream.sse_manager, "subscribe", subscribe)
    token = "invalid" if case == "invalid_token" else create_access_token(user.id)
    response = await async_client.get("/stream/notifications", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == (401 if case == "invalid_token" else 200)
    if case == "inactive":
        assert "event: notification" in response.text
