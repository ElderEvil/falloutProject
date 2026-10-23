from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient

from app.api.deps import get_redis_client
from app.core.config import settings
from app.services.oauth_service import OAuthService
from main import app

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.fixture(autouse=True)
def enabled_github(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", "github-id")
    monkeypatch.setattr(settings, "GITHUB_CLIENT_SECRET", "github-secret")


@pytest.mark.asyncio
async def test_provider_cancellation_consumes_state(async_client: AsyncClient, _shared_fake_redis):
    service = OAuthService()
    url, _ = await service.start("github", None, _shared_fake_redis)
    state = parse_qs(urlparse(url).query)["state"][0]

    response = await async_client.get(f"auth/oauth/github/callback?error=access_denied&state={state}")

    assert response.status_code == 302
    assert "error=access_denied" in response.headers["location"]
    assert await _shared_fake_redis.exists(f"oauth_state:{state}") == 0


@pytest.mark.asyncio
async def test_callback_without_code_or_state_redirects(async_client: AsyncClient):
    response = await async_client.get("auth/oauth/github/callback")

    assert response.status_code == 302
    assert "error=state_invalid" in response.headers["location"]


@pytest.mark.asyncio
async def test_cancellation_redis_failure_redirects(async_client: AsyncClient):
    class _BrokenRedis:
        async def getdel(self, _key):
            raise ConnectionError("redis down")

    app.dependency_overrides[get_redis_client] = lambda: _BrokenRedis()
    try:
        response = await async_client.get("auth/oauth/github/callback?error=access_denied&state=abc")
    finally:
        app.dependency_overrides.pop(get_redis_client, None)

    assert response.status_code == 302
    assert "error=oauth_failed" in response.headers["location"]
