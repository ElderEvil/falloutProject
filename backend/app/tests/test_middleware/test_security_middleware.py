import pytest
from guard import SecurityConfig
from guard.middleware import SecurityMiddleware
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.config import settings
from app.middleware.security import _AUTH_ENDPOINT_RATE_LIMITS, create_security_config


def test_create_security_config_uses_trusted_proxy_and_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "IPINFO_TOKEN", None, raising=False)
    monkeypatch.setattr(settings, "SECURITY_TRUSTED_PROXIES", ["10.42.0.0/16"], raising=False)

    config = create_security_config()

    assert config.geo_ip_handler is None
    assert "x-forwarded-for" in config.excluded_detection_headers
    assert config.trusted_proxies == ("10.42.0.0/16",)
    assert config.trusted_proxy_depth == 1
    assert config.redis_fail_open is True
    assert config.endpoint_rate_limits == _AUTH_ENDPOINT_RATE_LIMITS
    assert config.rate_limit == settings.RATE_LIMIT_REQUESTS
    assert config.security_headers["custom"]["Cross-Origin-Resource-Policy"] == "cross-origin"
    assert config.enable_penetration_detection is False


@pytest.mark.asyncio
async def test_guard_rate_limits_the_forwarded_client_ip() -> None:
    async def probe(request) -> PlainTextResponse:
        return PlainTextResponse(request.client.host if request.client else "unknown")

    app = Starlette(routes=[Route("/probe", probe)])
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["127.0.0.1"])
    app.add_middleware(
        SecurityMiddleware,
        config=SecurityConfig(
            rate_limit=2,
            rate_limit_window=60,
            enable_redis=False,
            trusted_proxies=("127.0.0.1",),
            trusted_proxy_depth=1,
            enable_penetration_detection=False,
            enable_ip_banning=False,
            excluded_detection_headers={"x-forwarded-for"},
        ),
    )

    transport = ASGITransport(app=app, client=("127.0.0.1", 1234))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/probe", headers={"X-Forwarded-For": "198.51.100.10"})).status_code == 200
        assert (await client.get("/probe", headers={"X-Forwarded-For": "198.51.100.10"})).status_code == 200
        assert (await client.get("/probe", headers={"X-Forwarded-For": "198.51.100.10"})).status_code == 429
        assert (await client.get("/probe", headers={"X-Forwarded-For": "198.51.100.11"})).status_code == 200
