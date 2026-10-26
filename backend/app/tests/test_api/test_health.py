"""Tests for the liveness and readiness endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.health_check import HealthCheckResult, ServiceStatus


def _result(service: str, status: ServiceStatus) -> HealthCheckResult:
    return HealthCheckResult(service=service, status=status, message=status.value)


@pytest.mark.asyncio
async def test_readiness_is_ready_when_critical_dependencies_are_healthy(async_client: AsyncClient) -> None:
    results = {
        "postgresql": _result("postgresql", ServiceStatus.HEALTHY),
        "redis": _result("redis", ServiceStatus.HEALTHY),
    }

    with patch(
        "main.HealthCheckService.check_all_services",
        new_callable=AsyncMock,
        return_value=results,
    ) as mocked:
        response = await async_client.get("https://testserver/readiness")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert set(response.json()["services"]) == {"postgresql", "redis"}
    assert mocked.call_args.kwargs == {"include_dramatiq": False, "include_rustfs": False}


@pytest.mark.asyncio
async def test_readiness_returns_503_when_a_critical_dependency_is_unhealthy(async_client: AsyncClient) -> None:
    results = {
        "postgresql": _result("postgresql", ServiceStatus.UNHEALTHY),
        "redis": _result("redis", ServiceStatus.HEALTHY),
    }

    with patch(
        "main.HealthCheckService.check_all_services",
        new_callable=AsyncMock,
        return_value=results,
    ):
        response = await async_client.get("https://testserver/readiness")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["services"]["postgresql"]["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_liveness_stays_lightweight_and_does_not_probe_dependencies(async_client: AsyncClient) -> None:
    with patch("main.HealthCheckService.check_all_services", new_callable=AsyncMock) as mocked:
        response = await async_client.get("https://testserver/healthcheck")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mocked.assert_not_awaited()
