"""OAuth first-login registration owns a single transaction boundary (real session).

The service commits once; a failure at a later write leaves no user, profile or link.
"""

from urllib.parse import parse_qs, urlparse

import fakeredis.aioredis
import httpx
import pytest
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.user import UserCreate
from app.services.oauth_service import OAuthService
from app.tests.test_services._transaction_helpers import counting_commit, fail_sql

pytestmark = pytest.mark.asyncio

EMAIL = "ada@gmail.com"
SUBJECT = "google-1"


@pytest.fixture
def redis_client():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture(autouse=True)
def oauth_settings(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "google-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "google-secret")


def _google_transport(email: str = EMAIL) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "access"})
        if request.url.path.endswith("/userinfo"):
            payload = {"sub": SUBJECT, "email": email, "email_verified": True, "name": "Ada Lovelace"}
            return httpx.Response(200, json=payload)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _inserts_provider_link(statement: str) -> bool:
    return statement.lower().startswith("insert into oauth_account")


async def _sign_in(service: OAuthService, session: AsyncSession, redis) -> User:
    url, browser_token = await service.start("google", None, redis)
    state = parse_qs(urlparse(url).query)["state"][0]
    return await service.complete("google", "code", state, browser_token, session, redis)


async def _users_by_email(session: AsyncSession, email: str) -> list[User]:
    return list((await session.execute(select(User).where(User.email == email))).scalars().all())


async def _links(session: AsyncSession) -> list[OAuthAccount]:
    query = select(OAuthAccount).where(
        OAuthAccount.provider == "google",
        OAuthAccount.provider_user_id == SUBJECT,
    )
    return list((await session.execute(query)).scalars().all())


async def test_first_login_commits_once_and_creates_user_profile_and_link(
    async_session: AsyncSession, redis_client
) -> None:
    service = OAuthService(transport=_google_transport())
    commits = counting_commit(async_session)
    user = await _sign_in(service, async_session, redis_client)

    assert len(commits) == 1, f"first login committed {len(commits)} times; the service owns exactly one"
    users = await _users_by_email(async_session, EMAIL)
    assert len(users) == 1
    assert user.id == users[0].id
    links = await _links(async_session)
    assert len(links) == 1
    assert links[0].user_id == user.id
    profiles = (await async_session.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalars().all()
    assert len(profiles) == 1


async def test_failure_at_provider_link_write_leaves_no_user_and_no_link(
    async_session: AsyncSession, redis_client
) -> None:
    service = OAuthService(transport=_google_transport())
    with pytest.raises(RuntimeError, match="injected provider link write failure"):
        async with fail_sql(async_session, _inserts_provider_link, "injected provider link write failure"):
            await _sign_in(service, async_session, redis_client)

    await async_session.rollback()
    assert await _users_by_email(async_session, EMAIL) == [], "a failed first login must not leave a user row"
    assert await _links(async_session) == [], "a failed first login must not leave a provider link"
    assert (await async_session.execute(select(UserProfile))).scalars().all() == []


async def test_username_conflict_does_not_discard_the_callers_staged_rows(
    async_session: AsyncSession, redis_client
) -> None:
    """A failed attempt isolates itself; it never rolls back rows the caller staged."""
    base = "adalovelace"
    await crud.user.create(
        db_session=async_session,
        obj_in=UserCreate(username=base, password="Secret123!", email="taken@example.com"),
    )
    await async_session.commit()
    staged = await crud.user.create(
        db_session=async_session,
        obj_in=UserCreate(username=f"{base}2", password="Secret123!", email="staged@example.com"),
        commit=False,
    )
    staged_id = staged.id

    service = OAuthService(transport=_google_transport())
    user = await _sign_in(service, async_session, redis_client)

    assert user.username == f"{base}3", "the conflicting candidates must be retried, not reused"
    assert await crud.user.get(async_session, staged_id) is not None, (
        "registration rolled back rows the caller had staged in the same transaction"
    )


async def test_existing_provider_link_signs_in_without_duplicates(async_session: AsyncSession, redis_client) -> None:
    service = OAuthService(transport=_google_transport())
    first = await _sign_in(service, async_session, redis_client)
    second = await _sign_in(service, async_session, redis_client)

    assert second.id == first.id
    assert len(await _users_by_email(async_session, EMAIL)) == 1
    assert len(await _links(async_session)) == 1
    profiles = (await async_session.execute(select(UserProfile).where(UserProfile.user_id == first.id))).scalars().all()
    assert len(profiles) == 1
    assert await crud.oauth_account.get_by_provider_subject(async_session, "google", SUBJECT) is not None
