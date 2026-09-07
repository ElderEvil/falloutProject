"""Tests for health check service."""

from __future__ import annotations

import logging
import sys
from typing import Literal, cast
from unittest.mock import AsyncMock, MagicMock, patch

import aiosmtplib
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


def test_check_rustfs_not_configured_missing_key() -> None:
    """RustFS has access key but no secret key."""
    with (
        patch.object(settings, "RUSTFS_ACCESS_KEY", "fake-key"),
        patch.object(settings, "RUSTFS_SECRET_KEY", None),
    ):
        result = HealthCheckService.check_rustfs()

    assert result.status == ServiceStatus.DEGRADED


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


# =============================================================================
# check_local_ai
# =============================================================================


def _local_ai_response(status_code: int, models: list[str] | None = None) -> MagicMock:
    mock_response = MagicMock()
    mock_response.status_code = status_code
    if models is not None:
        mock_response.json.return_value = {"data": [{"id": model} for model in models]}
    return mock_response


def _local_ai_client(get_effect: MagicMock | Exception) -> MagicMock:
    """AsyncClient mock whose .get returns get_effect, or raises it when given an exception."""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    if isinstance(get_effect, Exception):
        mock_client.get = AsyncMock(side_effect=get_effect)
    else:
        mock_client.get = AsyncMock(return_value=get_effect)
    return mock_client


@pytest.mark.parametrize("provider", [pytest.param("ollama", id="ollama"), pytest.param("lmstudio", id="lmstudio")])
@pytest.mark.asyncio
async def test_check_local_ai_not_configured(provider: Literal["ollama", "lmstudio"]) -> None:
    """AI_PROVIDER is not the checked local provider."""
    with patch.object(settings, "AI_PROVIDER", "openai"):
        result = await HealthCheckService.check_local_ai(provider)

    assert result.service == provider
    assert result.status == ServiceStatus.DEGRADED
    assert "not configured" in result.message
    assert result.details is not None
    assert result.details["ai_provider"] == "openai"


@pytest.fixture
def local_ai_provider(request: pytest.FixtureRequest) -> Literal["ollama", "lmstudio"]:
    """Patch settings for the parametrized local AI provider and yield its name."""
    provider: Literal["ollama", "lmstudio"] = request.param
    base_url = "http://localhost:11434/v1" if provider == "ollama" else "http://localhost:1234/v1"
    with (
        patch.object(settings, "AI_PROVIDER", provider),
        patch.object(settings, f"{provider.upper()}_BASE_URL", base_url),
        patch.object(settings, "AI_MODEL", "llama2"),
    ):
        yield provider


@pytest.mark.parametrize(
    ("local_ai_provider", "get_effect", "expected_status", "message_fragment"),
    [
        pytest.param(
            "ollama",
            _local_ai_response(200, ["llama2:latest", "mistral:7b"]),
            ServiceStatus.HEALTHY,
            "llama2",
            id="ollama-healthy",
        ),
        pytest.param(
            "ollama",
            _local_ai_response(200, ["mistral:7b"]),
            ServiceStatus.DEGRADED,
            "not found",
            id="ollama-model-not-found",
        ),
        pytest.param("ollama", _local_ai_response(503), ServiceStatus.UNHEALTHY, "503", id="ollama-unexpected-status"),
        pytest.param(
            "ollama",
            httpx.ConnectError("connection refused"),
            ServiceStatus.UNHEALTHY,
            "Cannot connect",
            id="ollama-connect-error",
        ),
        pytest.param(
            "ollama", httpx.TimeoutException("timeout"), ServiceStatus.UNHEALTHY, "timed out", id="ollama-timeout"
        ),
        pytest.param(
            "ollama", Exception("unknown error"), ServiceStatus.UNHEALTHY, "unknown error", id="ollama-generic-error"
        ),
        pytest.param(
            "lmstudio",
            _local_ai_response(200, ["llama2:latest"]),
            ServiceStatus.HEALTHY,
            "llama2",
            id="lmstudio-healthy",
        ),
        pytest.param(
            "lmstudio", _local_ai_response(200, []), ServiceStatus.DEGRADED, "not found", id="lmstudio-model-not-found"
        ),
        pytest.param(
            "lmstudio", _local_ai_response(503), ServiceStatus.UNHEALTHY, "503", id="lmstudio-unexpected-status"
        ),
        pytest.param(
            "lmstudio",
            httpx.ConnectError("connection refused"),
            ServiceStatus.UNHEALTHY,
            "Cannot connect",
            id="lmstudio-connect-error",
        ),
        pytest.param(
            "lmstudio", httpx.TimeoutException("timeout"), ServiceStatus.UNHEALTHY, "timed out", id="lmstudio-timeout"
        ),
        pytest.param(
            "lmstudio",
            Exception("unknown error"),
            ServiceStatus.UNHEALTHY,
            "unknown error",
            id="lmstudio-generic-error",
        ),
    ],
    indirect=["local_ai_provider"],
)
@pytest.mark.asyncio
async def test_check_local_ai_provider_responses(
    local_ai_provider: Literal["ollama", "lmstudio"],
    get_effect: MagicMock | Exception,
    expected_status: ServiceStatus,
    message_fragment: str,
) -> None:
    """check_local_ai maps local provider HTTP outcomes onto component health."""
    with patch("app.services.health_check.httpx.AsyncClient", return_value=_local_ai_client(get_effect)):
        result = await HealthCheckService.check_local_ai(local_ai_provider)

    assert result.service == local_ai_provider
    assert result.status == expected_status
    assert message_fragment in result.message


# =============================================================================
# check_smtp
# =============================================================================


@pytest.mark.parametrize(
    ("smtp_user", "smtp_password", "expected_auth", "login_args"),
    [
        pytest.param(None, None, False, None, id="no-auth"),
        pytest.param("user", "pass", True, ("user", "pass"), id="with-auth"),
    ],
)
@pytest.mark.asyncio
async def test_check_smtp_healthy(
    smtp_user: str | None, smtp_password: str | None, expected_auth: bool, login_args: tuple[str, str] | None
) -> None:
    """SMTP connects (and authenticates when credentials are set)."""
    mock_smtp = MagicMock()
    mock_smtp.connect = AsyncMock()
    mock_smtp.login = AsyncMock()
    mock_smtp.quit = AsyncMock()

    with (
        patch("app.services.health_check.aiosmtplib.SMTP", return_value=mock_smtp),
        patch.object(settings, "SMTP_USER", smtp_user),
        patch.object(settings, "SMTP_PASSWORD", smtp_password),
    ):
        result = await HealthCheckService.check_smtp()

    assert result.service == "smtp"
    assert result.status == ServiceStatus.HEALTHY
    assert "successful" in result.message
    assert result.details is not None
    assert result.details["auth"] is expected_auth
    mock_smtp.connect.assert_called_once()
    mock_smtp.quit.assert_called_once()
    if login_args is not None:
        mock_smtp.login.assert_called_once_with(*login_args)


@pytest.mark.parametrize(
    ("connect_error", "message_fragment"),
    [
        pytest.param(aiosmtplib.SMTPException("error"), "failed", id="smtp-exception"),
        pytest.param(TimeoutError("timed out"), "timed out", id="timeout"),
        pytest.param(ConnectionError("refused"), "failed", id="connection-error"),
    ],
)
@pytest.mark.asyncio
async def test_check_smtp_connect_failures(connect_error: Exception, message_fragment: str) -> None:
    """check_smtp maps connect failures onto UNHEALTHY."""
    mock_smtp = MagicMock()
    mock_smtp.connect = AsyncMock(side_effect=connect_error)

    with patch("app.services.health_check.aiosmtplib.SMTP", return_value=mock_smtp):
        result = await HealthCheckService.check_smtp()

    assert result.status == ServiceStatus.UNHEALTHY
    assert message_fragment in result.message


@pytest.mark.parametrize(
    ("tls", "ssl", "port", "expected_tls_key", "forbidden_tls_key"),
    [
        pytest.param(True, False, 465, "use_tls", "start_tls", id="implicit-tls"),
        pytest.param(False, True, 587, "start_tls", "use_tls", id="starttls"),
    ],
)
@pytest.mark.asyncio
async def test_check_smtp_tls_mapping(
    tls: bool, ssl: bool, port: int, expected_tls_key: str, forbidden_tls_key: str
) -> None:
    """SMTP_TLS/SMTP_SSL map to aiosmtplib use_tls vs start_tls."""
    with patch("app.services.health_check.aiosmtplib.SMTP") as mock_smtp_class:
        mock_smtp_class.return_value.connect = AsyncMock()
        mock_smtp_class.return_value.quit = AsyncMock()
        with (
            patch.object(settings, "SMTP_TLS", new=tls),
            patch.object(settings, "SMTP_SSL", new=ssl),
            patch.object(settings, "SMTP_HOST", "smtp.example.com"),
            patch.object(settings, "SMTP_PORT", port),
        ):
            result = await HealthCheckService.check_smtp()

    assert result.status == ServiceStatus.HEALTHY
    kwargs = mock_smtp_class.call_args.kwargs
    assert kwargs[expected_tls_key] is True
    assert forbidden_tls_key not in kwargs
    assert kwargs["port"] == port


# =============================================================================
# check_all_services
# =============================================================================


@pytest.mark.asyncio
async def test_check_all_services_with_local_ai() -> None:
    """With include_local_ai=True and a local provider configured."""
    service = HealthCheckService()

    async def fake_local_ai(provider: Literal["ollama", "lmstudio"]) -> HealthCheckResult:
        return _ok_result(provider)

    _pg = staticmethod(AsyncMock(return_value=_ok_result("postgresql")))
    _rd = staticmethod(AsyncMock(return_value=_ok_result("redis")))
    _rf = staticmethod(lambda: _ok_result("rustfs"))
    _dq = staticmethod(lambda: _ok_result("dramatiq"))
    _sm = staticmethod(AsyncMock(return_value=_ok_result("smtp")))
    _ai = staticmethod(fake_local_ai)
    with (
        patch.object(HealthCheckService, "check_postgres", _pg),
        patch.object(HealthCheckService, "check_redis", _rd),
        patch.object(HealthCheckService, "check_rustfs", _rf),
        patch.object(HealthCheckService, "check_dramatiq", _dq),
        patch.object(HealthCheckService, "check_smtp", _sm),
        patch.object(HealthCheckService, "check_local_ai", _ai),
        patch.object(settings, "AI_PROVIDER", "ollama"),
    ):
        engine = cast("AsyncEngine", object())
        results = await service.check_all_services(
            engine=engine, include_dramatiq=True, include_smtp=True, include_local_ai=True
        )

    assert "ollama" in results
    assert results["ollama"].status == ServiceStatus.HEALTHY


# =============================================================================
# log_health_check_results
# =============================================================================


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


def test_log_health_check_results_empty() -> None:
    """Empty results dict returns True (no unhealthy services)."""
    results: dict[str, HealthCheckResult] = {}
    overall = HealthCheckService.log_health_check_results(results)
    assert overall is True


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
