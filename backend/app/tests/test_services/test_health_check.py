"""Tests for health check service."""

from __future__ import annotations

import logging
import sys
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from botocore.exceptions import EndpointConnectionError
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import settings
from app.services.health_check import (
    HealthCheckResult,
    HealthCheckService,
    ServiceStatus,
)


def _ok_result(service: str) -> HealthCheckResult:
    return HealthCheckResult(service=service, status=ServiceStatus.HEALTHY, message="ok")


def _unhealthy_result(service: str) -> HealthCheckResult:
    return HealthCheckResult(service=service, status=ServiceStatus.UNHEALTHY, message="fail")


# =============================================================================
# check_postgres
# =============================================================================


@pytest.mark.asyncio
async def test_check_postgres_healthy() -> None:
    """Database returns SELECT 1 successfully."""
    mock_conn = MagicMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock()
    mock_engine = MagicMock(spec=AsyncEngine)
    mock_engine.connect.return_value = mock_conn

    result = await HealthCheckService.check_postgres(mock_engine)

    assert result.service == "postgresql"
    assert result.status == ServiceStatus.HEALTHY
    assert "successful" in result.message
    assert result.details is not None
    assert result.details["database"] == settings.POSTGRES_DB


@pytest.mark.asyncio
async def test_check_postgres_unhealthy() -> None:
    """Database connection fails with ConnectionError."""
    mock_engine = MagicMock(spec=AsyncEngine)
    mock_engine.connect.side_effect = ConnectionError("connection refused")

    result = await HealthCheckService.check_postgres(mock_engine)

    assert result.service == "postgresql"
    assert result.status == ServiceStatus.UNHEALTHY
    assert "failed" in result.message


# =============================================================================
# check_redis
# =============================================================================


@pytest.mark.asyncio
async def test_check_redis_healthy() -> None:
    """Redis ping succeeds."""
    mock_redis = MagicMock()
    mock_redis.ping = AsyncMock()
    mock_redis.close = AsyncMock()

    with patch("app.services.health_check.Redis", return_value=mock_redis):
        result = await HealthCheckService.check_redis()

    assert result.service == "redis"
    assert result.status == ServiceStatus.HEALTHY
    assert "successful" in result.message


@pytest.mark.asyncio
async def test_check_redis_unhealthy_redis_error() -> None:
    """Redis ping raises RedisError."""
    mock_redis = MagicMock()
    mock_redis.ping = AsyncMock(side_effect=RedisError("connection refused"))
    mock_redis.close = AsyncMock()

    with patch("app.services.health_check.Redis", return_value=mock_redis):
        result = await HealthCheckService.check_redis()

    assert result.service == "redis"
    assert result.status == ServiceStatus.UNHEALTHY
    assert "failed" in result.message


@pytest.mark.asyncio
async def test_check_redis_unhealthy_connection_error() -> None:
    """Redis ping raises ConnectionError."""
    mock_redis = MagicMock()
    mock_redis.ping = AsyncMock(side_effect=ConnectionError("refused"))
    mock_redis.close = AsyncMock()

    with patch("app.services.health_check.Redis", return_value=mock_redis):
        result = await HealthCheckService.check_redis()

    assert result.status == ServiceStatus.UNHEALTHY


# =============================================================================
# check_dramatiq
# =============================================================================


def test_check_dramatiq_not_configured() -> None:
    """Dramatiq broker is None (not imported)."""
    with patch("app.services.health_check.broker", None):
        result = HealthCheckService.check_dramatiq()

    assert result.service == "dramatiq"
    assert result.status == ServiceStatus.DEGRADED
    assert "not configured" in result.message
    assert result.details is not None
    assert result.details["actors"] == 0


def test_check_dramatiq_healthy() -> None:
    """Dramatiq broker has registered actors."""
    mock_broker = MagicMock()
    mock_broker.actors = {"actor_a": None, "actor_b": None}
    with patch("app.services.health_check.broker", mock_broker):
        result = HealthCheckService.check_dramatiq()

    assert result.service == "dramatiq"
    assert result.status == ServiceStatus.HEALTHY
    assert result.details is not None
    assert result.details["actors"] == 2
    assert result.details["actor_names"] == ["actor_a", "actor_b"]


def test_check_dramatiq_unhealthy() -> None:
    """Dramatiq broker.actors access raises a RedisError."""

    class BadBroker:
        @property
        def actors(self) -> dict:
            raise RedisError("broker down")

    with patch("app.services.health_check.broker", BadBroker()):
        result = HealthCheckService.check_dramatiq()

    assert result.service == "dramatiq"
    assert result.status == ServiceStatus.UNHEALTHY
    assert "failed" in result.message


def test_check_dramatiq_healthy_empty_actors() -> None:
    """Broker has zero actors but is healthy."""
    mock_broker = MagicMock()
    mock_broker.actors = {}
    with patch("app.services.health_check.broker", mock_broker):
        result = HealthCheckService.check_dramatiq()

    assert result.status == ServiceStatus.HEALTHY
    assert result.details is not None
    assert result.details["actors"] == 0


# =============================================================================
# check_rustfs
# =============================================================================


def _inject_fake_boto3(
    return_buckets: list[str] | None = None,
    side_effect: BaseException | None = None,
) -> MagicMock:
    """Inject a fake boto3 module so the inline ``import boto3`` succeeds."""
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    if side_effect:
        mock_client.list_buckets.side_effect = side_effect
    else:
        mock_client.list_buckets.return_value = {"Buckets": [{"Name": n} for n in (return_buckets or [])]}
    mock_boto3.client.return_value = mock_client
    return mock_boto3


def _patch_boto3_in_sys_modules(
    return_buckets: list[str] | None = None,
    side_effect: BaseException | None = None,
) -> dict:
    """Return a dict for patch.dict(sys.modules, ...) with fake boto3 and botocore."""
    return {
        "boto3": _inject_fake_boto3(return_buckets=return_buckets, side_effect=side_effect),
        "botocore.config": MagicMock(),
        "botocore.exceptions": MagicMock(),
    }


def test_check_rustfs_not_configured() -> None:
    """RustFS is not configured (no access key)."""
    with (
        patch.object(settings, "RUSTFS_ACCESS_KEY", None),
        patch.object(settings, "RUSTFS_SECRET_KEY", None),
    ):
        result = HealthCheckService.check_rustfs()

    assert result.service == "rustfs"
    assert result.status == ServiceStatus.DEGRADED
    assert "not configured" in result.message
    assert result.details is not None
    assert result.details["configured"] is False


def test_check_rustfs_not_configured_missing_key() -> None:
    """RustFS has access key but no secret key."""
    with (
        patch.object(settings, "RUSTFS_ACCESS_KEY", "fake-key"),
        patch.object(settings, "RUSTFS_SECRET_KEY", None),
    ):
        result = HealthCheckService.check_rustfs()

    assert result.status == ServiceStatus.DEGRADED


def test_check_rustfs_healthy() -> None:
    """RustFS lists buckets successfully."""
    fake_modules = _patch_boto3_in_sys_modules(return_buckets=["bucket1", "bucket2"])
    with (
        patch.dict(sys.modules, fake_modules),
        patch.object(settings, "RUSTFS_ACCESS_KEY", "fake-key"),
        patch.object(settings, "RUSTFS_SECRET_KEY", "fake-secret"),
        patch.object(settings, "RUSTFS_HOSTNAME", "s3.example.com"),
        patch.object(settings, "RUSTFS_PORT", "9000"),
        patch.object(settings, "RUSTFS_USE_HTTPS", new=False),
    ):
        result = HealthCheckService.check_rustfs()

    assert result.service == "rustfs"
    assert result.status == ServiceStatus.HEALTHY
    assert "successful" in result.message
    assert result.details is not None
    assert result.details["buckets"] == ["bucket1", "bucket2"]
    assert result.details["endpoint"] == "http://s3.example.com:9000"


def test_check_rustfs_healthy_default_hostname() -> None:
    """Endpoint built with default hostname and HTTPS."""
    fake_modules = _patch_boto3_in_sys_modules(return_buckets=[])
    with (
        patch.dict(sys.modules, fake_modules),
        patch.object(settings, "RUSTFS_ACCESS_KEY", "fake-key"),
        patch.object(settings, "RUSTFS_SECRET_KEY", "fake-secret"),
        patch.object(settings, "RUSTFS_HOSTNAME", None),
        patch.object(settings, "RUSTFS_PORT", ""),
        patch.object(settings, "RUSTFS_USE_HTTPS", new=True),
    ):
        result = HealthCheckService.check_rustfs()

    assert result.service == "rustfs"
    assert result.status == ServiceStatus.HEALTHY
    assert result.details is not None
    assert result.details["endpoint"] == "https://s3.evillab.dev"


def test_check_rustfs_client_error() -> None:
    """RustFS list_buckets raises a ClientError."""
    from botocore.exceptions import ClientError

    error = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}},
        "ListBuckets",
    )
    with (
        patch.dict(sys.modules, _patch_boto3_in_sys_modules(side_effect=error)),
        patch.object(settings, "RUSTFS_ACCESS_KEY", "fake-key"),
        patch.object(settings, "RUSTFS_SECRET_KEY", "fake-secret"),
        patch.object(settings, "RUSTFS_HOSTNAME", "s3.example.com"),
        patch.object(settings, "RUSTFS_PORT", ""),
        patch.object(settings, "RUSTFS_USE_HTTPS", new=False),
    ):
        result = HealthCheckService.check_rustfs()

    assert result.status == ServiceStatus.DEGRADED
    assert "failed" in result.message


def test_check_rustfs_import_error() -> None:
    """RustFS raises ImportError (boto3 not installed)."""
    with (
        patch.object(settings, "RUSTFS_ACCESS_KEY", "fake-key"),
        patch.object(settings, "RUSTFS_SECRET_KEY", "fake-secret"),
        patch.object(settings, "RUSTFS_HOSTNAME", "s3.example.com"),
        patch.object(settings, "RUSTFS_PORT", ""),
        patch.object(settings, "RUSTFS_USE_HTTPS", new=False),
        patch.dict(sys.modules, {"boto3": None}),
    ):
        # Simulate the inline ``import boto3`` raising ImportError
        builtins_import = __import__

        def _fake_import(name: str, *args, **kwargs) -> object:
            if name == "boto3":
                raise ImportError("no boto3")
            return builtins_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_fake_import):
            result = HealthCheckService.check_rustfs()

    assert result.status == ServiceStatus.DEGRADED
    assert "failed" in result.message


def test_check_rustfs_os_error() -> None:
    """RustFS raises OSError when connecting."""
    with (
        patch.dict(sys.modules, _patch_boto3_in_sys_modules(side_effect=OSError("network unreachable"))),
        patch.object(settings, "RUSTFS_ACCESS_KEY", "fake-key"),
        patch.object(settings, "RUSTFS_SECRET_KEY", "fake-secret"),
        patch.object(settings, "RUSTFS_HOSTNAME", "s3.example.com"),
        patch.object(settings, "RUSTFS_PORT", ""),
        patch.object(settings, "RUSTFS_USE_HTTPS", new=False),
    ):
        result = HealthCheckService.check_rustfs()

    assert result.status == ServiceStatus.DEGRADED
    assert "failed" in result.message


def test_check_rustfs_endpoint_connection_error_is_degraded() -> None:
    """An unreachable optional homelab endpoint must never abort backend startup."""
    error = EndpointConnectionError(endpoint_url="https://s3-api.evillab.dev:443/")
    with (
        patch.dict(sys.modules, _patch_boto3_in_sys_modules(side_effect=error)),
        patch.object(settings, "RUSTFS_ACCESS_KEY", "fake-key"),
        patch.object(settings, "RUSTFS_SECRET_KEY", "fake-secret"),
        patch.object(settings, "RUSTFS_HOSTNAME", "s3-api.evillab.dev"),
        patch.object(settings, "RUSTFS_PORT", "443"),
        patch.object(settings, "RUSTFS_USE_HTTPS", new=True),
    ):
        result = HealthCheckService.check_rustfs()

    assert result.status == ServiceStatus.DEGRADED
    assert "optional service" in result.message


# =============================================================================
# check_ollama
# =============================================================================


@pytest.mark.asyncio
async def test_check_ollama_not_configured() -> None:
    """AI_PROVIDER is not ollama."""
    with patch.object(settings, "AI_PROVIDER", "openai"):
        result = await HealthCheckService.check_ollama()

    assert result.service == "ollama"
    assert result.status == ServiceStatus.DEGRADED
    assert "not configured" in result.message
    assert result.details is not None
    assert result.details["ai_provider"] == "openai"


@pytest.mark.asyncio
async def test_check_ollama_healthy_model_available() -> None:
    """Ollama responds with models and configured model is found."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"id": "llama2:latest"}, {"id": "mistral:7b"}]}

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    with (
        patch.object(settings, "AI_PROVIDER", "ollama"),
        patch.object(settings, "OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        patch.object(settings, "AI_MODEL", "llama2"),
        patch("app.services.health_check.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await HealthCheckService.check_ollama()

    assert result.service == "ollama"
    assert result.status == ServiceStatus.HEALTHY
    assert "llama2" in result.message


@pytest.mark.asyncio
async def test_check_ollama_model_not_found() -> None:
    """Ollama responds but configured model is not available."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"id": "mistral:7b"}]}

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    with (
        patch.object(settings, "AI_PROVIDER", "ollama"),
        patch.object(settings, "OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        patch.object(settings, "AI_MODEL", "llama2"),
        patch("app.services.health_check.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await HealthCheckService.check_ollama()

    assert result.service == "ollama"
    assert result.status == ServiceStatus.DEGRADED
    assert "not found" in result.message


@pytest.mark.asyncio
async def test_check_ollama_unexpected_status() -> None:
    """Ollama returns non-200 status."""
    mock_response = MagicMock()
    mock_response.status_code = 503

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    with (
        patch.object(settings, "AI_PROVIDER", "ollama"),
        patch.object(settings, "OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        patch("app.services.health_check.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await HealthCheckService.check_ollama()

    assert result.status == ServiceStatus.UNHEALTHY
    assert "503" in result.message


@pytest.mark.asyncio
async def test_check_ollama_connect_error() -> None:
    """httpx.ConnectError raised."""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    with (
        patch.object(settings, "AI_PROVIDER", "ollama"),
        patch.object(settings, "OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        patch("app.services.health_check.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await HealthCheckService.check_ollama()

    assert result.status == ServiceStatus.UNHEALTHY
    assert "Cannot connect" in result.message


@pytest.mark.asyncio
async def test_check_ollama_timeout() -> None:
    """httpx.TimeoutException raised."""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

    with (
        patch.object(settings, "AI_PROVIDER", "ollama"),
        patch.object(settings, "OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        patch("app.services.health_check.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await HealthCheckService.check_ollama()

    assert result.status == ServiceStatus.UNHEALTHY
    assert "timed out" in result.message


@pytest.mark.asyncio
async def test_check_ollama_generic_exception() -> None:
    """Generic Exception (not ConnectError/TimeoutException) raised."""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(side_effect=Exception("unknown error"))

    with (
        patch.object(settings, "AI_PROVIDER", "ollama"),
        patch.object(settings, "OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        patch("app.services.health_check.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await HealthCheckService.check_ollama()

    assert result.status == ServiceStatus.UNHEALTHY
    assert "unknown error" in result.message


# =============================================================================
# check_smtp
# =============================================================================


@pytest.mark.asyncio
async def test_check_smtp_healthy_no_auth() -> None:
    """SMTP connects without auth."""
    mock_smtp = MagicMock()
    mock_smtp.connect = AsyncMock()
    mock_smtp.quit = AsyncMock()

    with (
        patch("app.services.health_check.aiosmtplib.SMTP", return_value=mock_smtp),
        patch.object(settings, "SMTP_USER", None),
    ):
        result = await HealthCheckService.check_smtp()

    assert result.service == "smtp"
    assert result.status == ServiceStatus.HEALTHY
    assert "successful" in result.message
    assert result.details is not None
    assert result.details["auth"] is False
    mock_smtp.connect.assert_called_once()
    mock_smtp.quit.assert_called_once()


@pytest.mark.asyncio
async def test_check_smtp_healthy_with_auth() -> None:
    """SMTP connects and authenticates."""
    mock_smtp = MagicMock()
    mock_smtp.connect = AsyncMock()
    mock_smtp.login = AsyncMock()
    mock_smtp.quit = AsyncMock()

    with (
        patch("app.services.health_check.aiosmtplib.SMTP", return_value=mock_smtp),
        patch.object(settings, "SMTP_USER", "user"),
        patch.object(settings, "SMTP_PASSWORD", "pass"),
    ):
        result = await HealthCheckService.check_smtp()

    assert result.status == ServiceStatus.HEALTHY
    assert result.details is not None
    assert result.details["auth"] is True
    mock_smtp.login.assert_called_once_with("user", "pass")


@pytest.mark.asyncio
async def test_check_smtp_unhealthy_smtp_exception() -> None:
    """SMTPException raised on connect."""
    import aiosmtplib

    mock_smtp = MagicMock()
    mock_smtp.connect = AsyncMock(side_effect=aiosmtplib.SMTPException("error"))

    with patch("app.services.health_check.aiosmtplib.SMTP", return_value=mock_smtp):
        result = await HealthCheckService.check_smtp()

    assert result.status == ServiceStatus.UNHEALTHY
    assert "failed" in result.message


@pytest.mark.asyncio
async def test_check_smtp_unhealthy_timeout() -> None:
    """TimeoutError raised on connect."""
    mock_smtp = MagicMock()
    mock_smtp.connect = AsyncMock(side_effect=TimeoutError("timed out"))

    with patch("app.services.health_check.aiosmtplib.SMTP", return_value=mock_smtp):
        result = await HealthCheckService.check_smtp()

    assert result.status == ServiceStatus.UNHEALTHY
    assert "timed out" in result.message


@pytest.mark.asyncio
async def test_check_smtp_unhealthy_connection_error() -> None:
    """ConnectionError raised on connect."""
    mock_smtp = MagicMock()
    mock_smtp.connect = AsyncMock(side_effect=ConnectionError("refused"))

    with patch("app.services.health_check.aiosmtplib.SMTP", return_value=mock_smtp):
        result = await HealthCheckService.check_smtp()

    assert result.status == ServiceStatus.UNHEALTHY
    assert "failed" in result.message


# =============================================================================
# check_all_services
# =============================================================================


@pytest.mark.asyncio
async def test_check_all_services_all_enabled() -> None:
    """All services enabled: postgres, redis, rustfs, dramatiq, smtp."""
    service = HealthCheckService()

    async def fake_postgres(_engine: AsyncEngine) -> HealthCheckResult:
        return _ok_result("postgresql")

    async def fake_redis() -> HealthCheckResult:
        return _ok_result("redis")

    def fake_rustfs() -> HealthCheckResult:
        return _ok_result("rustfs")

    def fake_dramatiq() -> HealthCheckResult:
        return _ok_result("dramatiq")

    async def fake_smtp() -> HealthCheckResult:
        return _ok_result("smtp")

    with (
        patch.object(HealthCheckService, "check_postgres", staticmethod(fake_postgres)),
        patch.object(HealthCheckService, "check_redis", staticmethod(fake_redis)),
        patch.object(HealthCheckService, "check_rustfs", staticmethod(fake_rustfs)),
        patch.object(HealthCheckService, "check_dramatiq", staticmethod(fake_dramatiq)),
        patch.object(HealthCheckService, "check_smtp", staticmethod(fake_smtp)),
    ):
        engine = cast("AsyncEngine", object())
        results = await service.check_all_services(
            engine=engine, include_dramatiq=True, include_smtp=True, include_ollama=False
        )

    assert "postgresql" in results
    assert "redis" in results
    assert "rustfs" in results
    assert "dramatiq" in results
    assert "smtp" in results
    assert "ollama" not in results
    for r in results.values():
        assert r.status == ServiceStatus.HEALTHY


@pytest.mark.asyncio
async def test_check_all_services_with_ollama() -> None:
    """With include_ollama=True."""
    service = HealthCheckService()

    async def fake_ollama() -> HealthCheckResult:
        return _ok_result("ollama")

    _pg = staticmethod(AsyncMock(return_value=_ok_result("postgresql")))
    _rd = staticmethod(AsyncMock(return_value=_ok_result("redis")))
    _rf = staticmethod(lambda: _ok_result("rustfs"))
    _dq = staticmethod(lambda: _ok_result("dramatiq"))
    _sm = staticmethod(AsyncMock(return_value=_ok_result("smtp")))
    _ol = staticmethod(fake_ollama)
    with (
        patch.object(HealthCheckService, "check_postgres", _pg),
        patch.object(HealthCheckService, "check_redis", _rd),
        patch.object(HealthCheckService, "check_rustfs", _rf),
        patch.object(HealthCheckService, "check_dramatiq", _dq),
        patch.object(HealthCheckService, "check_smtp", _sm),
        patch.object(HealthCheckService, "check_ollama", _ol),
    ):
        engine = cast("AsyncEngine", object())
        results = await service.check_all_services(
            engine=engine, include_dramatiq=True, include_smtp=True, include_ollama=True
        )

    assert "ollama" in results
    assert results["ollama"].status == ServiceStatus.HEALTHY


@pytest.mark.asyncio
async def test_check_all_services_dramatiq_disabled() -> None:
    """When include_dramatiq=False."""
    service = HealthCheckService()

    _pg = staticmethod(AsyncMock(return_value=_ok_result("postgresql")))
    _rd = staticmethod(AsyncMock(return_value=_ok_result("redis")))
    _rf = staticmethod(lambda: _ok_result("rustfs"))
    _sm = staticmethod(AsyncMock(return_value=_ok_result("smtp")))
    with (
        patch.object(HealthCheckService, "check_postgres", _pg),
        patch.object(HealthCheckService, "check_redis", _rd),
        patch.object(HealthCheckService, "check_rustfs", _rf),
        patch.object(HealthCheckService, "check_smtp", _sm),
    ):
        engine = cast("AsyncEngine", object())
        results = await service.check_all_services(
            engine=engine, include_dramatiq=False, include_smtp=True, include_ollama=False
        )

    assert "dramatiq" not in results


@pytest.mark.asyncio
async def test_check_all_services_smtp_disabled() -> None:
    """When include_smtp=False."""
    service = HealthCheckService()

    _pg = staticmethod(AsyncMock(return_value=_ok_result("postgresql")))
    _rd = staticmethod(AsyncMock(return_value=_ok_result("redis")))
    _rf = staticmethod(lambda: _ok_result("rustfs"))
    _dq = staticmethod(lambda: _ok_result("dramatiq"))
    with (
        patch.object(HealthCheckService, "check_postgres", _pg),
        patch.object(HealthCheckService, "check_redis", _rd),
        patch.object(HealthCheckService, "check_rustfs", _rf),
        patch.object(HealthCheckService, "check_dramatiq", _dq),
    ):
        engine = cast("AsyncEngine", object())
        results = await service.check_all_services(
            engine=engine, include_dramatiq=True, include_smtp=False, include_ollama=False
        )

    assert "smtp" not in results


@pytest.mark.asyncio
async def test_check_all_services_rustfs_disabled() -> None:
    """Startup can skip optional RustFS so an unavailable homelab never delays readiness."""
    service = HealthCheckService()
    _pg = staticmethod(AsyncMock(return_value=_ok_result("postgresql")))
    _rd = staticmethod(AsyncMock(return_value=_ok_result("redis")))
    _sm = staticmethod(AsyncMock(return_value=_ok_result("smtp")))
    _dq = staticmethod(lambda: _ok_result("dramatiq"))

    with (
        patch.object(HealthCheckService, "check_postgres", _pg),
        patch.object(HealthCheckService, "check_redis", _rd),
        patch.object(HealthCheckService, "check_rustfs") as rustfs,
        patch.object(HealthCheckService, "check_smtp", _sm),
        patch.object(HealthCheckService, "check_dramatiq", _dq),
    ):
        engine = cast("AsyncEngine", object())
        results = await service.check_all_services(engine=engine, include_rustfs=False)

    assert "rustfs" not in results
    rustfs.assert_not_called()


@pytest.mark.asyncio
async def test_check_all_services_mixed_health() -> None:
    """Some services healthy, some unhealthy."""
    service = HealthCheckService()

    async def fake_unhealthy(_engine: AsyncEngine) -> HealthCheckResult:
        return _unhealthy_result("postgresql")

    _ok = _ok_result
    _un = _unhealthy_result
    _rd = staticmethod(AsyncMock(return_value=_ok("redis")))
    _dq = staticmethod(lambda: _ok("dramatiq"))
    _sm = staticmethod(AsyncMock(return_value=_ok("smtp")))
    _rf = staticmethod(lambda: _un("rustfs"))
    with (
        patch.object(HealthCheckService, "check_postgres", staticmethod(fake_unhealthy)),
        patch.object(HealthCheckService, "check_redis", _rd),
        patch.object(HealthCheckService, "check_rustfs", _rf),
        patch.object(HealthCheckService, "check_dramatiq", _dq),
        patch.object(HealthCheckService, "check_smtp", _sm),
    ):
        engine = cast("AsyncEngine", object())
        results = await service.check_all_services(
            engine=engine, include_dramatiq=True, include_smtp=True, include_ollama=False
        )

    assert results["postgresql"].status == ServiceStatus.UNHEALTHY
    assert results["rustfs"].status == ServiceStatus.UNHEALTHY
    assert results["redis"].status == ServiceStatus.HEALTHY


# =============================================================================
# log_health_check_results
# =============================================================================


def test_log_health_check_all_healthy() -> None:
    """All services healthy returns True."""
    results = {
        "postgresql": _ok_result("postgresql"),
        "redis": _ok_result("redis"),
    }

    with patch.object(logging.getLogger("app.services.health_check"), "info") as mock_info:
        overall = HealthCheckService.log_health_check_results(results)

    assert overall is True
    # Should log the header, individual results, and the "all healthy" summary
    assert mock_info.call_count >= 3


def test_log_health_check_some_unhealthy() -> None:
    """Mixed results returns False; unhealthy service logged via logger.log(level, ...)."""
    results = {
        "postgresql": _ok_result("postgresql"),
        "redis": _unhealthy_result("redis"),
    }

    logger_instance = logging.getLogger("app.services.health_check")
    with patch.object(logger_instance, "info") as mock_info, patch.object(logger_instance, "warning") as mock_warning:
        overall = HealthCheckService.log_health_check_results(results)

    assert overall is False
    # The unhealthy result line uses logger.log(logging.WARNING, ...) — not logger.warning().
    # Only the final summary line uses logger.warning() directly, so warning() is called once.
    assert mock_warning.call_count == 1
    # info calls include header banners + individual healthy result line
    assert mock_info.call_count >= 2


def test_log_health_check_all_unhealthy() -> None:
    """All services unhealthy returns False."""
    results = {
        "postgresql": _unhealthy_result("postgresql"),
        "redis": _unhealthy_result("redis"),
    }
    overall = HealthCheckService.log_health_check_results(results)
    assert overall is False


def test_log_health_check_results_empty() -> None:
    """Empty results dict returns True (no unhealthy services)."""
    results: dict[str, HealthCheckResult] = {}
    overall = HealthCheckService.log_health_check_results(results)
    assert overall is True


def test_log_health_check_degraded_status() -> None:
    """DEGRADED status marks overall as unhealthy."""
    results = {
        "postgresql": _ok_result("postgresql"),
        "rustfs": HealthCheckResult(
            service="rustfs",
            status=ServiceStatus.DEGRADED,
            message="not configured",
        ),
    }
    overall = HealthCheckService.log_health_check_results(results)
    assert overall is False


# =============================================================================
# Helper classes and enums
# =============================================================================


def test_service_status_enum() -> None:
    """Verify ServiceStatus enum values."""
    assert ServiceStatus.HEALTHY == "healthy"
    assert ServiceStatus.UNHEALTHY == "unhealthy"
    assert ServiceStatus.DEGRADED == "degraded"


def test_health_check_result_creation() -> None:
    """HealthCheckResult dataclass creation with optional fields."""
    result = HealthCheckResult(
        service="test",
        status=ServiceStatus.HEALTHY,
        message="All good",
        details={"key": "value"},
    )
    assert result.service == "test"
    assert result.status == ServiceStatus.HEALTHY
    assert result.message == "All good"
    assert result.details == {"key": "value"}

    # details default to None
    result_no_details = HealthCheckResult(service="test2", status=ServiceStatus.UNHEALTHY, message="Bad")
    assert result_no_details.details is None
