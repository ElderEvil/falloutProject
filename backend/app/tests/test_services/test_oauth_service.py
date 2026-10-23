from urllib.parse import parse_qs, urlparse

import fakeredis.aioredis
import httpx
import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.user import UserCreate
from app.services.oauth_service import OAuthService
from app.utils.exceptions import OAuthFlowError


@pytest.fixture
def redis_client():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture(autouse=True)
def oauth_settings(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "google-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", "github-id")
    monkeypatch.setattr(settings, "GITHUB_CLIENT_SECRET", "github-secret")


def _google_transport(email: str = "ada@gmail.com", hd: str | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "access"})
        if request.url.path.endswith("/userinfo"):
            payload = {"sub": "google-1", "email": email, "email_verified": True, "name": "Ada Lovelace"}
            if hd:
                payload["hd"] = hd
            return httpx.Response(200, json=payload)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _github_transport(email: str = "octo@example.com") -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": "access"})
        if request.url.path == "/user":
            return httpx.Response(200, json={"id": 42, "login": "octocat"})
        if request.url.path == "/user/emails":
            return httpx.Response(200, json=[{"email": email, "primary": True, "verified": True}])
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _state(url: str) -> str:
    return parse_qs(urlparse(url).query)["state"][0]


async def test_start_builds_pkce_state_and_redirect(redis_client):
    service = OAuthService(transport=_google_transport())

    url, browser_token = await service.start("google", None, redis_client)

    params = parse_qs(urlparse(url).query)
    assert params["code_challenge_method"] == ["S256"]
    assert params["scope"] == ["openid email profile"]
    assert params["redirect_uri"] == ["http://localhost:8000/api/v1/auth/oauth/google/callback"]
    assert await redis_client.exists(f"oauth_state:{params['state'][0]}") == 1
    assert browser_token


async def test_state_is_single_use_and_cookie_bound(redis_client):
    service = OAuthService(transport=_google_transport())
    url, browser_token = await service.start("google", None, redis_client)
    state = _state(url)

    with pytest.raises(OAuthFlowError) as exc:
        await service.complete("google", "code", state, "other-browser", None, redis_client)
    assert exc.value.code == "state_invalid"

    with pytest.raises(OAuthFlowError):
        await service.complete("google", "code", state, browser_token, None, redis_client)


async def test_google_third_party_email_cannot_create_account(redis_client, async_session: AsyncSession):
    service = OAuthService(transport=_google_transport("ada@outlook.com"))
    url, browser_token = await service.start("google", None, redis_client)

    with pytest.raises(OAuthFlowError) as exc:
        await service.complete("google", "code", _state(url), browser_token, async_session, redis_client)

    assert exc.value.code == "email_verification_required"
    assert await crud.user.get_by_email(async_session, email="ada@outlook.com") is None


async def test_gmail_creates_passwordless_verified_user(redis_client, async_session: AsyncSession):
    service = OAuthService(transport=_google_transport("ada@gmail.com"))
    url, browser_token = await service.start("google", None, redis_client)

    user = await service.complete("google", "code", _state(url), browser_token, async_session, redis_client)

    assert user.hashed_password is None
    assert user.email_verified is True
    link = await crud.oauth_account.get_by_provider_subject(async_session, "google", "google-1")
    assert link is not None
    assert link.user_id == user.id


async def test_github_primary_verified_email_is_used(redis_client, async_session: AsyncSession):
    service = OAuthService(transport=_github_transport())
    url, browser_token = await service.start("github", None, redis_client)

    user = await service.complete("github", "code", _state(url), browser_token, async_session, redis_client)

    assert user.email == "octo@example.com"
    assert user.email_verified is True


async def test_verified_local_account_links_under_lock(redis_client, async_session: AsyncSession):
    local = await crud.user.create(
        async_session,
        obj_in=UserCreate(username="localada", password="Secret123!", email="ada@gmail.com"),
    )
    local.email_verified = True
    await async_session.commit()
    original_hash = local.hashed_password

    service = OAuthService(transport=_google_transport("ada@gmail.com"))
    url, browser_token = await service.start("google", None, redis_client)
    user = await service.complete("google", "code", _state(url), browser_token, async_session, redis_client)

    assert user.id == local.id
    link = await crud.oauth_account.get_for_user(async_session, local.id, "google")
    assert link is not None
    await async_session.refresh(local)
    assert local.hashed_password == original_hash


async def test_handoff_is_single_use_and_browser_bound(redis_client, async_session: AsyncSession):
    user = await crud.user.create(
        async_session,
        obj_in=UserCreate(username="handoff", password="Secret123!", email="handoff@example.com"),
    )
    service = OAuthService()

    stolen = await service.create_handoff(user.id, "browser-a", redis_client)
    with pytest.raises(OAuthFlowError) as exc:
        await service.redeem_handoff(stolen, "browser-b", async_session, redis_client)
    assert exc.value.code == "handoff_invalid"

    code = await service.create_handoff(user.id, "browser-a", redis_client)
    token = await service.redeem_handoff(code, "browser-a", async_session, redis_client)
    assert token.access_token
    with pytest.raises(OAuthFlowError):
        await service.redeem_handoff(code, "browser-a", async_session, redis_client)


async def test_unverified_local_account_is_not_linked(redis_client, async_session: AsyncSession):
    local = await crud.user.create(
        async_session,
        obj_in=UserCreate(username="unverified", password="Secret123!", email="ada@gmail.com"),
    )
    service = OAuthService(transport=_google_transport("ada@gmail.com"))
    url, browser_token = await service.start("google", None, redis_client)

    with pytest.raises(OAuthFlowError) as exc:
        await service.complete("google", "code", _state(url), browser_token, async_session, redis_client)

    assert exc.value.code == "local_account_unverified"
    assert await crud.oauth_account.get_for_user(async_session, local.id, "google") is None


async def test_registration_closed_rejects_new_identity(redis_client, async_session: AsyncSession, monkeypatch):
    monkeypatch.setattr(settings, "USERS_OPEN_REGISTRATION", False)
    service = OAuthService(transport=_google_transport("new@gmail.com"))
    url, browser_token = await service.start("google", None, redis_client)

    with pytest.raises(OAuthFlowError) as exc:
        await service.complete("google", "code", _state(url), browser_token, async_session, redis_client)

    assert exc.value.code == "registration_closed"
    assert await crud.user.get_by_email(async_session, email="new@gmail.com") is None


async def test_expired_and_wrong_provider_state_are_rejected(redis_client):
    service = OAuthService(transport=_google_transport())
    url, browser_token = await service.start("google", None, redis_client)
    state = _state(url)
    await redis_client.delete(f"oauth_state:{state}")

    with pytest.raises(OAuthFlowError) as exc:
        await service.complete("google", "code", state, browser_token, None, redis_client)
    assert exc.value.code == "state_invalid"

    url, browser_token = await service.start("google", None, redis_client)
    with pytest.raises(OAuthFlowError) as exc:
        await service.complete("github", "code", _state(url), browser_token, None, redis_client)
    assert exc.value.code == "state_invalid"


async def test_inactive_and_deleted_linked_users_are_rejected(redis_client, async_session: AsyncSession):
    service = OAuthService(transport=_google_transport("ada@gmail.com"))
    user = await crud.user.create(
        async_session,
        obj_in=UserCreate(username="inactive", password="Secret123!", email="ada@gmail.com"),
    )
    user.email_verified = True
    user.is_active = False
    await async_session.commit()
    await crud.oauth_account.link_to_user(
        async_session, user_id=user.id, provider="google", provider_user_id="google-1"
    )
    url, browser_token = await service.start("google", None, redis_client)
    with pytest.raises(OAuthFlowError) as exc:
        await service.complete("google", "code", _state(url), browser_token, async_session, redis_client)
    assert exc.value.code == "account_inactive"

    user.is_active = True
    user.is_deleted = True
    await async_session.commit()
    url, browser_token = await service.start("google", None, redis_client)
    with pytest.raises(OAuthFlowError) as exc:
        await service.complete("google", "code", _state(url), browser_token, async_session, redis_client)
    assert exc.value.code == "account_deleted"


def test_username_candidates_include_planned_fallback():
    from app.services.oauth_service import _username_candidates

    candidates = _username_candidates("overseer")
    assert "overseer6" in candidates
    assert "overseer99" in candidates
    assert any(candidate.startswith("overseer_") and len(candidate) == len("overseer_") + 4 for candidate in candidates)


async def test_adding_password_preserves_provider_login(redis_client, async_session: AsyncSession):
    from app.core.security import get_password_hash

    service = OAuthService(transport=_google_transport("ada@gmail.com"))
    url, browser_token = await service.start("google", None, redis_client)
    user = await service.complete("google", "code", _state(url), browser_token, async_session, redis_client)

    user.hashed_password = get_password_hash("NewPass123!")
    await async_session.commit()

    url, browser_token = await service.start("google", None, redis_client)
    again = await service.complete("google", "code", _state(url), browser_token, async_session, redis_client)

    assert again.id == user.id
    assert again.has_password is True


async def test_second_provider_keeps_same_user(redis_client, async_session: AsyncSession):
    github = OAuthService(transport=_github_transport("shared@gmail.com"))
    url, browser_token = await github.start("github", None, redis_client)
    user = await github.complete("github", "code", _state(url), browser_token, async_session, redis_client)

    google = OAuthService(transport=_google_transport("shared@gmail.com"))
    url, browser_token = await google.start("google", None, redis_client)
    again = await google.complete("google", "code", _state(url), browser_token, async_session, redis_client)

    assert again.id == user.id
    assert await crud.oauth_account.get_for_user(async_session, user.id, "github") is not None
    assert await crud.oauth_account.get_for_user(async_session, user.id, "google") is not None


async def test_email_change_preserves_provider_login(redis_client, async_session: AsyncSession):
    service = OAuthService(transport=_google_transport("ada@gmail.com"))
    url, browser_token = await service.start("google", None, redis_client)
    user = await service.complete("google", "code", _state(url), browser_token, async_session, redis_client)

    user.email = "changed@example.com"
    await async_session.commit()

    url, browser_token = await service.start("google", None, redis_client)
    again = await service.complete("google", "code", _state(url), browser_token, async_session, redis_client)

    assert again.id == user.id
