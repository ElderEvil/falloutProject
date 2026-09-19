"""Admin configuration regression and authenticated render smoke tests."""

from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.admin.views import (
    DwellerAdmin,
    GameStateAdmin,
    ItemAdmin,
    LLInteractionAdmin,
    PromptAdmin,
    QuestAdmin,
    UserAdmin,
    VaultAdmin,
)
from app.core.config import settings
from app.models.dweller import Dweller
from app.models.llm_interaction import LLMInteraction
from app.models.prompt import Prompt
from app.models.user import User
from app.models.vault import Vault
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
    for view in (GameStateAdmin, QuestAdmin):
        assert view.can_create is False
        assert view.can_edit is False
        assert view.can_delete is False


def test_generic_item_admin_exposes_inventory_location() -> None:
    from app.models import Item

    assert {Item.name, Item.item_type, Item.storage} <= set(ItemAdmin.column_list)


def test_llm_and_prompt_views_are_read_only() -> None:
    for view in (LLInteractionAdmin, PromptAdmin):
        assert view.can_create is False
        assert view.can_edit is False
        assert view.can_delete is False
        assert view.can_export is False


def test_ai_audit_views_expose_targeted_search_and_filters() -> None:
    assert {Prompt.prompt_name, Prompt.description} <= set(PromptAdmin.column_searchable_list)
    assert {filter_.column for filter_ in PromptAdmin.column_filters} == {Prompt.is_active, Prompt.version}
    assert {filter_.column for filter_ in LLInteractionAdmin.column_filters} == {
        LLMInteraction.usage,
        LLMInteraction.provider,
        LLMInteraction.model,
    }


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


def test_vault_admin_exposes_incidents_disabled_column_and_filter() -> None:
    assert Vault.incidents_disabled in VaultAdmin.column_list
    assert {filter_.column for filter_ in VaultAdmin.column_filters} == {Vault.incidents_disabled}


def test_vault_admin_sorting_covers_scalar_columns() -> None:
    assert set(VaultAdmin.column_sortable_list) == {
        Vault.number,
        Vault.bottle_caps,
        Vault.happiness,
        Vault.power,
        Vault.power_max,
        Vault.food,
        Vault.food_max,
        Vault.water,
        Vault.water_max,
        Vault.population_max,
        Vault.created_at,
        Vault.updated_at,
    }
    assert VaultAdmin.column_default_sort == [(Vault.created_at, True)]


def test_vault_admin_exposes_incident_spawning_actions() -> None:
    for action_name in (
        "disable_incidents",
        "enable_incidents",
        "disable_incidents_all",
        "enable_incidents_all",
    ):
        assert hasattr(getattr(VaultAdmin, action_name), "_action")


async def test_disable_and_enable_incidents_for_all_vaults(
    admin_client: AsyncClient,
    vault: Vault,
    async_session: AsyncSession,
    db_connection: AsyncConnection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.user import UserCreate
    from app.schemas.vault import VaultCreateWithUserID
    from app.tests.factory.vaults import random_vault_number

    test_session_maker = sessionmaker(bind=db_connection, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(VaultAdmin, "session_maker", test_session_maker)

    suffix = uuid4().hex[:8]
    user2 = await crud.user.create(
        db_session=async_session,
        obj_in=UserCreate(
            username=f"bulk-{suffix}", email=f"bulk-{suffix}@example.com", password="secret-password-123"
        ),
    )
    number = random_vault_number()
    while number == vault.number:
        number = random_vault_number()
    vault2 = await crud.vault.create(
        db_session=async_session,
        obj_in=VaultCreateWithUserID(
            number=number,
            bottle_caps=100,
            happiness=50,
            power=50,
            food=50,
            water=50,
            population_max=50,
            user_id=user2.id,
        ),
    )
    vault2.incidents_disabled = True
    async_session.add(vault2)
    await async_session.commit()

    response = await admin_client.get("/admin/vault/action/disable-incidents-all")
    assert response.status_code == 303
    await async_session.refresh(vault)
    await async_session.refresh(vault2)
    assert vault.incidents_disabled is True
    assert vault2.incidents_disabled is True

    response = await admin_client.get("/admin/vault/action/enable-incidents-all")
    assert response.status_code == 303
    await async_session.refresh(vault)
    await async_session.refresh(vault2)
    assert vault.incidents_disabled is False
    assert vault2.incidents_disabled is False
