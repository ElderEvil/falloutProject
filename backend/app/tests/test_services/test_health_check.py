from __future__ import annotations

import logging
import sys
from asyncio import run as asyncio_run
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import aiosmtplib
import httpx
import pytest
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import settings
from app.core.health_check import HealthCheckResult, HealthCheckService, ServiceStatus

HEALTH = "app.core.health_check"
OK = ServiceStatus.HEALTHY
BAD = ServiceStatus.UNHEALTHY
DEGRADED = ServiceStatus.DEGRADED


def _result(service: str, status: ServiceStatus = OK, message: str = "ok") -> HealthCheckResult:
    return HealthCheckResult(service=service, status=status, message=message)


def _fake_boto3(return_buckets: list[str] | None = None, side_effect: BaseException | None = None) -> dict:
    """Inject fake boto3/botocore modules so the inline ``import boto3`` succeeds."""
    client = MagicMock()
    if side_effect:
        client.list_buckets.side_effect = side_effect
    else:
        client.list_buckets.return_value = {"Buckets": [{"Name": n} for n in (return_buckets or [])]}
    boto3 = MagicMock()
    boto3.client.return_value = client
    return {"boto3": boto3, "botocore.config": MagicMock(), "botocore.exceptions": MagicMock()}


def _local_ai_response(status_code: int, models: list[str] | None = None) -> MagicMock:
    response = MagicMock(status_code=status_code)
    if models is not None:
        response.json.return_value = {"data": [{"id": model} for model in models]}
    return response


def _local_ai_client(get_effect) -> MagicMock:
    """AsyncClient mock whose .get returns get_effect, or raises it when given an exception."""
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.get = (
        AsyncMock(side_effect=get_effect) if isinstance(get_effect, Exception) else AsyncMock(return_value=get_effect)
    )
    return client


def test_check_postgres_healthy() -> None:
    conn = MagicMock(execute=AsyncMock())
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=None)
    engine = MagicMock(spec=AsyncEngine)
    engine.connect.return_value = conn

    result = asyncio_run(HealthCheckService.check_postgres(engine))

    assert result.service == "postgresql"
    assert result.status == OK
    assert "successful" in result.message
    assert result.details is not None
    assert result.details["database"] == settings.POSTGRES_DB


def test_check_postgres_unhealthy() -> None:
    engine = MagicMock(spec=AsyncEngine)
    engine.connect.side_effect = ConnectionError("connection refused")

    result = asyncio_run(HealthCheckService.check_postgres(engine))

    assert (result.service, result.status) == ("postgresql", BAD)
    assert "failed" in result.message


@pytest.mark.parametrize("ping_error", [None, RedisError("connection refused")])
def test_check_redis(ping_error) -> None:
    redis = MagicMock(ping=AsyncMock(side_effect=ping_error), close=AsyncMock())
    with patch(f"{HEALTH}.Redis", return_value=redis):
        result = asyncio_run(HealthCheckService.check_redis())

    assert result.service == "redis"
    assert result.status == (OK if ping_error is None else BAD)
    assert ("successful" if ping_error is None else "failed") in result.message


def test_check_redis_unhealthy_invalid_port() -> None:
    with patch.object(settings, "REDIS_PORT", "not-a-port"):
        result = asyncio_run(HealthCheckService.check_redis())

    assert (result.service, result.status) == ("redis", BAD)
    assert "failed" in result.message


def test_check_dramatiq_not_configured() -> None:
    with patch(f"{HEALTH}.broker", None):
        result = HealthCheckService.check_dramatiq()

    assert (result.service, result.status) == ("dramatiq", DEGRADED)
    assert "not configured" in result.message
    assert result.details is not None
    assert result.details["actors"] == 0


def test_check_dramatiq_unhealthy() -> None:
    class BadBroker:
        @property
        def actors(self) -> dict:
            raise RedisError("broker down")

    with patch(f"{HEALTH}.broker", BadBroker()):
        result = HealthCheckService.check_dramatiq()

    assert (result.service, result.status) == ("dramatiq", BAD)
    assert "failed" in result.message


def test_check_dramatiq_healthy_empty_actors() -> None:
    broker = MagicMock(actors={})
    with patch(f"{HEALTH}.broker", broker):
        result = HealthCheckService.check_dramatiq()

    assert result.status == OK
    assert result.details is not None
    assert result.details["actors"] == 0


def test_check_rustfs_not_configured_missing_key() -> None:
    with patch.object(settings, "RUSTFS_ACCESS_KEY", "fake-key"), patch.object(settings, "RUSTFS_SECRET_KEY", None):
        assert HealthCheckService.check_rustfs().status == DEGRADED


def test_check_rustfs_healthy_default_hostname() -> None:
    with (
        patch.dict(sys.modules, _fake_boto3(return_buckets=[])),
        patch.object(settings, "RUSTFS_ACCESS_KEY", "fake-key"),
        patch.object(settings, "RUSTFS_SECRET_KEY", "fake-secret"),
        patch.object(settings, "RUSTFS_HOSTNAME", None),
        patch.object(settings, "RUSTFS_PORT", ""),
        patch.object(settings, "RUSTFS_USE_HTTPS", new=True),
    ):
        result = HealthCheckService.check_rustfs()

    assert (result.service, result.status) == ("rustfs", OK)
    assert result.details is not None
    assert result.details["endpoint"] == "https://s3.evillab.dev"


def test_check_rustfs_os_error() -> None:
    with (
        patch.dict(sys.modules, _fake_boto3(side_effect=OSError("network unreachable"))),
        patch.object(settings, "RUSTFS_ACCESS_KEY", "fake-key"),
        patch.object(settings, "RUSTFS_SECRET_KEY", "fake-secret"),
        patch.object(settings, "RUSTFS_HOSTNAME", "s3.example.com"),
        patch.object(settings, "RUSTFS_PORT", ""),
        patch.object(settings, "RUSTFS_USE_HTTPS", new=False),
    ):
        result = HealthCheckService.check_rustfs()

    assert result.status == DEGRADED
    assert "failed" in result.message


@pytest.mark.parametrize("provider", ["ollama", "lmstudio"])
def test_check_local_ai_not_configured(provider: str) -> None:
    with patch.object(settings, "AI_PROVIDER", "openai"):
        result = asyncio_run(HealthCheckService.check_local_ai(provider))

    assert (result.service, result.status) == (provider, DEGRADED)
    assert "not configured" in result.message
    assert result.details is not None
    assert result.details["ai_provider"] == "openai"


@pytest.fixture
def local_ai_provider(request: pytest.FixtureRequest) -> str:
    """Patch settings for the parametrized local AI provider and yield its name."""
    provider: str = request.param
    base_url = "http://localhost:11434/v1" if provider == "ollama" else "http://localhost:1234/v1"
    with (
        patch.object(settings, "AI_PROVIDER", provider),
        patch.object(settings, f"{provider.upper()}_BASE_URL", base_url),
        patch.object(settings, "AI_MODEL", "llama2"),
    ):
        yield provider


LOCAL_AI_CASES = [
    pytest.param("ollama", _local_ai_response(200, ["llama2:latest", "mistral:7b"]), OK, "llama2", id="ollama-healthy"),
    pytest.param("ollama", _local_ai_response(200, ["mistral:7b"]), DEGRADED, "not found", id="ollama-model-missing"),
    pytest.param("ollama", _local_ai_response(503), BAD, "503", id="ollama-unexpected-status"),
    pytest.param("ollama", httpx.ConnectError("connection refused"), BAD, "Cannot connect", id="ollama-connect-error"),
    pytest.param("ollama", httpx.TimeoutException("timeout"), BAD, "timed out", id="ollama-timeout"),
    pytest.param("lmstudio", _local_ai_response(200, ["llama2:latest"]), OK, "llama2", id="lmstudio-healthy"),
    pytest.param("lmstudio", _local_ai_response(200, []), DEGRADED, "not found", id="lmstudio-model-missing"),
    pytest.param("lmstudio", _local_ai_response(503), BAD, "503", id="lmstudio-unexpected-status"),
    pytest.param(
        "lmstudio", httpx.ConnectError("connection refused"), BAD, "Cannot connect", id="lmstudio-connect-error"
    ),
    pytest.param("lmstudio", httpx.TimeoutException("timeout"), BAD, "timed out", id="lmstudio-timeout"),
]


@pytest.mark.parametrize(
    ("local_ai_provider", "get_effect", "expected_status", "fragment"), LOCAL_AI_CASES, indirect=["local_ai_provider"]
)
def test_check_local_ai_provider_responses(
    local_ai_provider: str, get_effect, expected_status: ServiceStatus, fragment: str
) -> None:
    with patch(f"{HEALTH}.httpx.AsyncClient", return_value=_local_ai_client(get_effect)):
        result = asyncio_run(HealthCheckService.check_local_ai(local_ai_provider))

    assert result.service == local_ai_provider
    assert result.status == expected_status
    assert fragment in result.message


@pytest.mark.parametrize("local_ai_provider", ["ollama", "lmstudio"], indirect=True)
def test_check_local_ai_unexpected_error_propagates(local_ai_provider: str) -> None:
    """Non-HTTP, non-parse failures are bugs: they propagate instead of reporting UNHEALTHY."""
    with (
        patch(f"{HEALTH}.httpx.AsyncClient", return_value=_local_ai_client(Exception("boom"))),
        pytest.raises(Exception, match="boom"),
    ):
        asyncio_run(HealthCheckService.check_local_ai(local_ai_provider))


@pytest.mark.parametrize(
    ("smtp_user", "smtp_password", "expected_auth", "login_args"),
    [
        pytest.param(None, None, False, None, id="no-auth"),
        pytest.param("user", "pass", True, ("user", "pass"), id="auth"),
    ],
)
def test_check_smtp_healthy(smtp_user, smtp_password, expected_auth: bool, login_args) -> None:
    smtp = MagicMock(connect=AsyncMock(), login=AsyncMock(), quit=AsyncMock())
    with (
        patch(f"{HEALTH}.aiosmtplib.SMTP", return_value=smtp),
        patch.object(settings, "SMTP_USER", smtp_user),
        patch.object(settings, "SMTP_PASSWORD", smtp_password),
    ):
        result = asyncio_run(HealthCheckService.check_smtp())

    assert (result.service, result.status) == ("smtp", OK)
    assert "successful" in result.message
    assert result.details is not None
    assert result.details["auth"] is expected_auth
    smtp.connect.assert_called_once()
    smtp.quit.assert_called_once()
    if login_args is not None:
        smtp.login.assert_called_once_with(*login_args)


@pytest.mark.parametrize(
    ("connect_error", "fragment"),
    [
        pytest.param(aiosmtplib.SMTPException("error"), "failed", id="smtp-exception"),
        pytest.param(TimeoutError("timed out"), "timed out", id="timeout"),
        pytest.param(ConnectionError("refused"), "failed", id="connection-error"),
    ],
)
def test_check_smtp_connect_failures(connect_error: Exception, fragment: str) -> None:
    smtp = MagicMock(connect=AsyncMock(side_effect=connect_error))
    with patch(f"{HEALTH}.aiosmtplib.SMTP", return_value=smtp):
        result = asyncio_run(HealthCheckService.check_smtp())

    assert result.status == BAD
    assert fragment in result.message


@pytest.mark.parametrize(
    ("tls", "ssl", "port", "expected_tls_key", "forbidden_tls_key"),
    [
        pytest.param(True, False, 465, "use_tls", "start_tls", id="implicit-tls"),
        pytest.param(False, True, 587, "start_tls", "use_tls", id="starttls"),
    ],
)
def test_check_smtp_tls_mapping(tls: bool, ssl: bool, port: int, expected_tls_key: str, forbidden_tls_key: str) -> None:
    with patch(f"{HEALTH}.aiosmtplib.SMTP") as smtp_class:
        smtp_class.return_value.connect = AsyncMock()
        smtp_class.return_value.quit = AsyncMock()
        with (
            patch.object(settings, "SMTP_TLS", new=tls),
            patch.object(settings, "SMTP_SSL", new=ssl),
            patch.object(settings, "SMTP_HOST", "smtp.example.com"),
            patch.object(settings, "SMTP_PORT", port),
        ):
            result = asyncio_run(HealthCheckService.check_smtp())

    assert result.status == OK
    kwargs = smtp_class.call_args.kwargs
    assert kwargs[expected_tls_key] is True
    assert forbidden_tls_key not in kwargs
    assert kwargs["port"] == port


def test_check_all_services_with_local_ai() -> None:
    async def fake_local_ai(provider: str) -> HealthCheckResult:
        return _result(provider)

    with (
        patch.object(HealthCheckService, "check_postgres", AsyncMock(return_value=_result("postgresql"))),
        patch.object(HealthCheckService, "check_redis", AsyncMock(return_value=_result("redis"))),
        patch.object(HealthCheckService, "check_rustfs", staticmethod(lambda: _result("rustfs"))),
        patch.object(HealthCheckService, "check_dramatiq", staticmethod(lambda: _result("dramatiq"))),
        patch.object(HealthCheckService, "check_smtp", AsyncMock(return_value=_result("smtp"))),
        patch.object(HealthCheckService, "check_local_ai", staticmethod(fake_local_ai)),
        patch.object(settings, "AI_PROVIDER", "ollama"),
    ):
        results = asyncio_run(
            HealthCheckService().check_all_services(
                engine=cast("AsyncEngine", object()), include_dramatiq=True, include_smtp=True, include_local_ai=True
            )
        )

    assert "ollama" in results
    assert results["ollama"].status == OK


def test_log_health_check_some_unhealthy() -> None:
    results = {"postgresql": _result("postgresql"), "redis": _result("redis", BAD, "fail")}

    logger_instance = logging.getLogger(HEALTH)
    with patch.object(logger_instance, "info") as info, patch.object(logger_instance, "warning") as warning:
        overall = HealthCheckService.log_health_check_results(results)

    assert overall is False
    # The unhealthy result line uses logger.log(logging.WARNING, ...) — not logger.warning().
    # Only the final summary line uses logger.warning() directly, so warning() is called once.
    assert warning.call_count == 1
    assert info.call_count >= 2  # header banners + the individual healthy result line


def test_log_health_check_results_empty() -> None:
    assert HealthCheckService.log_health_check_results({}) is True


def test_service_status_enum() -> None:
    assert ServiceStatus.HEALTHY == "healthy"
    assert ServiceStatus.UNHEALTHY == "unhealthy"
    assert ServiceStatus.DEGRADED == "degraded"


def test_health_check_result_creation() -> None:
    result = HealthCheckResult(service="test", status=OK, message="All good", details={"key": "value"})
    assert (result.service, result.status, result.message, result.details) == (
        "test",
        OK,
        "All good",
        {"key": "value"},
    )
    assert HealthCheckResult(service="test2", status=BAD, message="Bad").details is None
