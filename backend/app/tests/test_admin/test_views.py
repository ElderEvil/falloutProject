"""Admin configuration regression and authenticated render smoke tests."""

from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.admin.views import (
    AISettingsAdmin,
    DwellerAdmin,
    GameStateAdmin,
    LLInteractionAdmin,
    PromptAdmin,
    QuestAdmin,
    UserAdmin,
)
from app.core.config import settings
from app.models.dweller import Dweller
from app.models.user import User
from main import app


def test_user_admin_never_exposes_credentials_or_recovery_tokens() -> None:
    assert {
        User.hashed_password,
        User.email_verification_token,
        User.password_reset_token,
        User.password_reset_expires,
    } <= set(UserAdmin.column_details_exclude_list)


def test_admin_views_disable_deletion_by_default() -> None:
    assert UserAdmin.can_delete is False
    assert QuestAdmin.can_delete is False


def test_operational_and_quest_data_views_are_read_only() -> None:
    for view in (AISettingsAdmin, GameStateAdmin, QuestAdmin):
        assert view.can_create is False
        assert view.can_edit is False
        assert view.can_delete is False


def test_llm_and_prompt_views_are_read_only() -> None:
    for view in (LLInteractionAdmin, PromptAdmin):
        assert view.can_create is False
        assert view.can_edit is False
        assert view.can_delete is False
        assert view.can_export is False


def test_user_admin_exposes_a_verify_email_action() -> None:
    assert hasattr(UserAdmin.verify_email, "_action")


@pytest_asyncio.fixture
async def admin_client(
    db_connection: AsyncConnection,
    superuser: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient]:
    """Superuser client for sqladmin pages, with admin DB access bound to the test database."""
    from app.admin import auth as admin_auth

    test_session_maker = sessionmaker(bind=db_connection, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(admin_auth, "async_engine", db_connection)
    for view in (DwellerAdmin, LLInteractionAdmin, PromptAdmin):
        monkeypatch.setattr(view, "session_maker", test_session_maker)

    # AdminAuth stores user_id as a session string; on PostgreSQL the driver
    # coerces it, SQLite's Uuid bind processor does not - mirror that leniency.
    real_user_get = crud.user.get

    async def user_get_with_str_uuid(db_session: AsyncSession, id: Any, **kwargs: Any) -> User:
        return await real_user_get(db_session, id=UUID(id) if isinstance(id, str) else id, **kwargs)

    monkeypatch.setattr(crud.user, "get", user_get_with_str_uuid)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as client:
        response = await client.post(
            "/admin/login",
            data={"username": settings.FIRST_SUPERUSER_EMAIL, "password": settings.FIRST_SUPERUSER_PASSWORD},
        )
        assert response.status_code == 302
        yield client


async def test_llm_interaction_admin_renders(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/admin/llm-interaction/list")
    assert response.status_code == 200


async def test_prompt_admin_renders(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/admin/prompt/list")
    assert response.status_code == 200


async def test_dweller_admin_bio_flag(
    admin_client: AsyncClient,
    dweller: Dweller,
    async_session: AsyncSession,
) -> None:
    assert Dweller.bio in DwellerAdmin.column_list
    dweller.bio = "x" * 80
    async_session.add(dweller)
    await async_session.commit()

    response = await admin_client.get("/admin/dweller/list")
    assert response.status_code == 200
    assert "..." in response.text
