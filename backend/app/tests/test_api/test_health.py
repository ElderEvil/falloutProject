"""Tests for the liveness and readiness endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.core.config import settings


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_service", [None, "postgresql", "redis"])
async def test_readiness_probes_only_critical_dependencies(
    async_client: AsyncClient,
    db_connection: AsyncConnection,
    monkeypatch: pytest.MonkeyPatch,
    failed_service: str | None,
) -> None:
    redis_client = AsyncMock()
    if failed_service == "redis":
        redis_client.ping.side_effect = RedisConnectionError("Redis unavailable")

    monkeypatch.setattr("main.async_engine", db_connection.engine)
    # An accidental optional probe must fail, even if local credentials are absent.
    monkeypatch.setattr(settings, "RUSTFS_ACCESS_KEY", "test-key")
    monkeypatch.setattr(settings, "RUSTFS_SECRET_KEY", "test-secret")
    monkeypatch.setattr("app.services.health_check.broker", object())
    with (
        patch("app.services.health_check.Redis", return_value=redis_client),
        patch("boto3.client", side_effect=AssertionError("Unexpected object storage probe")) as storage,
        patch("aiosmtplib.SMTP", side_effect=AssertionError("Unexpected SMTP probe")) as smtp,
        patch("httpx.AsyncClient", side_effect=AssertionError("Unexpected AI probe")) as ai,
    ):
        if failed_service == "postgresql":
            with patch.object(AsyncEngine, "connect", side_effect=ConnectionError("Database unavailable")):
                response = await async_client.get("https://testserver/readiness")
        else:
            response = await async_client.get("https://testserver/readiness")

    assert response.status_code == (503 if failed_service else 200)
    body = response.json()
    assert body["status"] == ("not_ready" if failed_service else "ready")
    assert set(body["services"]) == {"postgresql", "redis"}
    for service, result in body["services"].items():
        assert result["status"] == ("unhealthy" if service == failed_service else "healthy")
    redis_client.ping.assert_awaited_once()
    redis_client.close.assert_awaited_once()
    storage.assert_not_called()
    smtp.assert_not_called()
    ai.assert_not_called()


@pytest.mark.asyncio
async def test_liveness_stays_lightweight_and_does_not_probe_dependencies(async_client: AsyncClient) -> None:
    with (
        patch.object(AsyncEngine, "connect", side_effect=AssertionError("Unexpected database probe")),
        patch("app.services.health_check.Redis", side_effect=AssertionError("Unexpected Redis probe")),
    ):
        response = await async_client.get("https://testserver/healthcheck")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
