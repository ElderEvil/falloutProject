from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import settings
from app.services.health_check import HealthCheckResult, HealthCheckService, ServiceStatus


def _ok_result(service: str) -> HealthCheckResult:
    return HealthCheckResult(service=service, status=ServiceStatus.HEALTHY, message="ok")


@pytest.mark.asyncio
async def test_health_check_skips_minio_when_rustfs_provider(monkeypatch) -> None:
    async def check_postgres(_engine) -> HealthCheckResult:
        return _ok_result("postgresql")

    async def check_redis() -> HealthCheckResult:
        return _ok_result("redis")

    def check_rustfs() -> HealthCheckResult:
        return _ok_result("rustfs")

    monkeypatch.setattr(settings, "STORAGE_PROVIDER", "rustfs", raising=False)
    monkeypatch.setattr(HealthCheckService, "check_postgres", staticmethod(check_postgres))
    monkeypatch.setattr(HealthCheckService, "check_redis", staticmethod(check_redis))
    monkeypatch.setattr(HealthCheckService, "check_rustfs", staticmethod(check_rustfs))

    service = HealthCheckService()
    engine = cast(AsyncEngine, object())
    results = await service.check_all_services(engine=engine, include_celery=False, include_smtp=False)

    assert "minio" not in results
