from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
import pytest
from httpx import AsyncClient

from app import crud
from app.api.deps import get_redis_client
from app.core import security
from app.core.config import settings
from app.schemas.user import UserCreate
from app.services.oauth_service import OAUTH_BROWSER_COOKIE_NAME, OAuthService, oauth_service
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


async def _auth_headers(async_session, username: str):
    user = await crud.user.create(
        async_session,
        obj_in=UserCreate(
            username=username,
            password=f"Secret-{uuid4().hex}",
            email=f"{username}@example.com",
        ),
    )
    return user, {"Authorization": f"Bearer {security.create_access_token(user.id)}"}


def _github_link_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": "access"})
        if request.url.path == "/user":
            return httpx.Response(200, json={"id": 99, "login": "linker"})
        if request.url.path == "/user/emails":
            return httpx.Response(
                200,
                json=[{"email": "linked@example.com", "primary": True, "verified": True}],
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


async def test_linked_accounts_requires_authentication(async_client: AsyncClient):
    response = await async_client.get("auth/oauth/accounts")

    assert response.status_code == 401


async def test_linked_accounts_lists_providers_and_password(async_client: AsyncClient, async_session):
    user, headers = await _auth_headers(async_session, f"accounts{uuid4().hex[:8]}")

    response = await async_client.get("auth/oauth/accounts", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"providers": [], "has_password": True}
    assert user.hashed_password is not None


async def test_link_provider_requires_authentication(async_client: AsyncClient):
    response = await async_client.post("auth/oauth/github/link")

    assert response.status_code == 401


async def test_link_provider_returns_authorize_url_and_sets_browser_cookie(async_client: AsyncClient, async_session):
    _user, headers = await _auth_headers(async_session, f"linkstart{uuid4().hex[:8]}")

    response = await async_client.post("auth/oauth/github/link", headers=headers)

    assert response.status_code == 200
    assert response.json()["authorize_url"].startswith("https://github.com/login/oauth/authorize?")
    assert response.cookies.get(OAUTH_BROWSER_COOKIE_NAME)


async def test_unlink_provider_with_password_succeeds(async_client: AsyncClient, async_session):
    user, headers = await _auth_headers(async_session, f"unlinkapi{uuid4().hex[:8]}")
    await crud.oauth_account.link_to_user(
        async_session, user_id=user.id, provider="google", provider_user_id="unlink-api-google"
    )

    response = await async_client.delete("auth/oauth/google", headers=headers)

    assert response.status_code == 204
    assert await crud.oauth_account.get_for_user(async_session, user.id, "google") is None


async def test_unlink_provider_refuses_last_sign_in_method(async_client: AsyncClient, async_session):
    user, headers = await _auth_headers(async_session, f"lastapi{uuid4().hex[:8]}")
    user.hashed_password = None
    await async_session.commit()
    await crud.oauth_account.link_to_user(
        async_session, user_id=user.id, provider="google", provider_user_id="last-api-google"
    )

    response = await async_client.delete("auth/oauth/google", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "last_sign_in_method"
    assert await crud.oauth_account.get_for_user(async_session, user.id, "google") is not None


async def test_link_callback_redirects_to_profile_without_issuing_tokens(
    async_client: AsyncClient, async_session, _shared_fake_redis, monkeypatch
):
    user, _headers = await _auth_headers(async_session, f"linkcallback{uuid4().hex[:8]}")
    monkeypatch.setattr(oauth_service, "_transport", _github_link_transport())
    url, browser_token = await oauth_service.start_link("github", user.id, None, async_session, _shared_fake_redis)
    state = parse_qs(urlparse(url).query)["state"][0]
    async_client.cookies.set(OAUTH_BROWSER_COOKIE_NAME, browser_token)

    response = await async_client.get(f"auth/oauth/github/callback?code=code&state={state}")

    assert response.status_code == 302
    assert "linked=github" in response.headers["location"]
    link = await crud.oauth_account.get_for_user(async_session, user.id, "github")
    assert link is not None
    assert link.provider_user_id == "99"


async def test_link_callback_reports_provider_identity_in_use(
    async_client: AsyncClient, async_session, _shared_fake_redis, monkeypatch
):
    owner, _owner_headers = await _auth_headers(async_session, f"linkowner{uuid4().hex[:8]}")
    user, _headers = await _auth_headers(async_session, f"linkother{uuid4().hex[:8]}")
    await crud.oauth_account.link_to_user(async_session, user_id=owner.id, provider="github", provider_user_id="99")
    user_id = user.id
    monkeypatch.setattr(oauth_service, "_transport", _github_link_transport())
    url, browser_token = await oauth_service.start_link("github", user_id, None, async_session, _shared_fake_redis)
    state = parse_qs(urlparse(url).query)["state"][0]
    async_client.cookies.set(OAUTH_BROWSER_COOKIE_NAME, browser_token)

    response = await async_client.get(f"auth/oauth/github/callback?code=code&state={state}")

    assert response.status_code == 302
    assert "error=provider_identity_in_use" in response.headers["location"]
    assert await crud.oauth_account.get_for_user(async_session, user_id, "github") is None
