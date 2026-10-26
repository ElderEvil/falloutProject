"""Admin configuration regression and authenticated render smoke tests."""

import re
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.admin import actions as admin_actions
from app.admin.views import (
    AccountMergeAdmin,
    DwellerAdmin,
    GameStateAdmin,
    ItemAdmin,
    LLInteractionAdmin,
    MergeAccountsAdmin,
    PromptAdmin,
    QuestAdmin,
    TeamAdmin,
    TeamMemberAdmin,
    UserAdmin,
    VaultAdmin,
)
from app.core.config import settings
from app.core.enums import HazardTeam
from app.models.dweller import Dweller
from app.models.llm_interaction import LLMInteraction
from app.models.oauth_account import OAuthAccount
from app.models.prompt import Prompt
from app.models.team import ACTIVE_STATUS, Team, TeamMember
from app.models.user import User
from app.models.vault import Vault
from app.schemas.user import UserCreate
from app.tests.factory.vaults import random_vault_number
from main import admin, app

_CSRF_TOKEN_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


def _csrf_token_from(response: Any) -> str:
    match = _CSRF_TOKEN_RE.search(response.text)
    assert match is not None, "csrf token not found in the incidents page"
    return match.group(1)


def test_user_admin_never_exposes_credentials_or_recovery_tokens() -> None:
    assert UserAdmin.can_export is False
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
    for view in admin._views:
        monkeypatch.setattr(type(view), "session_maker", test_session_maker)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as client:
        response = await client.post(
            "/admin/login",
            data={"username": settings.FIRST_SUPERUSER_EMAIL, "password": settings.FIRST_SUPERUSER_PASSWORD},
        )
        assert response.status_code == 302
        yield client


async def test_dweller_bio_is_available_in_details_without_cluttering_list(
    admin_client: AsyncClient,
    dweller: Dweller,
    async_session: AsyncSession,
) -> None:
    assert "bio" not in [getattr(column, "key", column) for column in DwellerAdmin.column_list]
    dweller.bio = "x" * 80
    async_session.add(dweller)
    await async_session.commit()

    response = await admin_client.get("/admin/dweller/list")
    assert response.status_code == 200
    assert "x" * 80 not in response.text
    response = await admin_client.get(f"/admin/dweller/details/{dweller.id}")
    assert response.status_code == 200
    assert "x" * 80 in response.text


def test_vault_admin_exposes_incidents_disabled_column_and_filter() -> None:
    assert "incidents_disabled" in [getattr(column, "key", column) for column in VaultAdmin.column_list]
    assert "incidents_disabled" in {filter_.column for filter_ in VaultAdmin.column_filters}


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


def test_vault_admin_exposes_incident_toggle_page() -> None:
    assert VaultAdmin.incidents_page._exposed is True
    assert VaultAdmin.incidents_page._methods == ["GET"]
    assert VaultAdmin.incidents._exposed is True
    assert VaultAdmin.incidents._methods == ["POST"]


async def test_incident_toggle_page_renders_with_csrf_token(
    admin_client: AsyncClient,
    vault: Vault,
) -> None:
    response = await admin_client.get("/admin/vault/incidents")
    assert response.status_code == 200
    assert 'name="csrf_token"' in response.text
    assert str(vault.number) in response.text


async def test_incident_toggle_post_without_token_is_forbidden(
    admin_client: AsyncClient,
    vault: Vault,
    async_session: AsyncSession,
) -> None:
    response = await admin_client.post(
        "/admin/vault/incidents",
        data={"action": "disable", "scope": "selected", "vault_id": str(vault.id)},
    )
    assert response.status_code == 403
    await async_session.refresh(vault)
    assert vault.incidents_disabled is False


async def test_incident_toggle_post_with_wrong_token_is_forbidden(
    admin_client: AsyncClient,
    vault: Vault,
    async_session: AsyncSession,
) -> None:
    response = await admin_client.post(
        "/admin/vault/incidents",
        data={
            "action": "disable",
            "scope": "selected",
            "vault_id": str(vault.id),
            "csrf_token": "not-the-session-token",
        },
    )
    assert response.status_code == 403
    await async_session.refresh(vault)
    assert vault.incidents_disabled is False


async def test_incident_toggle_post_flips_selected_vaults(
    admin_client: AsyncClient,
    vault: Vault,
    async_session: AsyncSession,
) -> None:
    page = await admin_client.get("/admin/vault/incidents")
    assert page.status_code == 200
    token = _csrf_token_from(page)

    response = await admin_client.post(
        "/admin/vault/incidents",
        data={
            "action": "disable",
            "scope": "selected",
            "vault_id": str(vault.id),
            "csrf_token": token,
        },
    )
    assert response.status_code == 303
    await async_session.refresh(vault)
    assert vault.incidents_disabled is True

    response = await admin_client.post(
        "/admin/vault/incidents",
        data={
            "action": "enable",
            "scope": "selected",
            "vault_id": str(vault.id),
            "csrf_token": token,
        },
    )
    assert response.status_code == 303
    await async_session.refresh(vault)
    assert vault.incidents_disabled is False


async def test_incident_toggle_all_scope_flips_every_vault(
    admin_client: AsyncClient,
    vault: Vault,
    async_session: AsyncSession,
) -> None:
    from app.schemas.user import UserCreate
    from app.schemas.vault import VaultCreateWithUserID
    from app.tests.factory.vaults import random_vault_number

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

    page = await admin_client.get("/admin/vault/incidents")
    assert page.status_code == 200
    token = _csrf_token_from(page)

    response = await admin_client.post(
        "/admin/vault/incidents",
        data={"action": "disable", "scope": "all", "csrf_token": token},
    )
    assert response.status_code == 303
    await async_session.refresh(vault)
    await async_session.refresh(vault2)
    assert vault.incidents_disabled is True
    assert vault2.incidents_disabled is True

    response = await admin_client.post(
        "/admin/vault/incidents",
        data={"action": "enable", "scope": "all", "csrf_token": token},
    )
    assert response.status_code == 303
    await async_session.refresh(vault)
    await async_session.refresh(vault2)
    assert vault.incidents_disabled is False
    assert vault2.incidents_disabled is False


async def test_old_incident_action_urls_no_longer_mutate(
    admin_client: AsyncClient,
    vault: Vault,
    async_session: AsyncSession,
) -> None:
    response = await admin_client.get("/admin/vault/action/disable-incidents-all")
    assert response.status_code == 404
    await async_session.refresh(vault)
    assert vault.incidents_disabled is False


def test_team_admin_views_are_read_only() -> None:
    """Rosters are derived from gameplay; the admin view exists to inspect them."""
    for view in (TeamAdmin, TeamMemberAdmin):
        assert view.can_create is False
        assert view.can_edit is False
        assert view.can_delete is False


def test_team_admin_exposes_purpose_and_placement_columns() -> None:
    assert {Team.hazard_team, Team.quest_id, Team.incident_id, Team.vault} <= set(TeamAdmin.column_list)
    assert {TeamMember.team, TeamMember.dweller, TeamMember.slot_number, TeamMember.status} <= set(
        TeamMemberAdmin.column_list
    )


async def test_team_admin_pages_render(admin_client: AsyncClient) -> None:
    for view in (TeamAdmin, TeamMemberAdmin):
        response = await admin_client.get(f"/admin/{view.identity}/list")
        assert response.status_code == 200, view.identity


async def test_team_admin_lists_an_earned_roster(
    admin_client: AsyncClient,
    async_session: AsyncSession,
    room_with_dwellers: dict,
) -> None:
    """An earned hazard place is visible in the admin roster, so the team can be tracked."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    team = await crud.team_crud.get_or_create_hazard_team(async_session, room.vault_id, HazardTeam.FIRE)
    async_session.add(TeamMember(team_id=team.id, dweller_id=dweller.id, status=ACTIVE_STATUS, slot_number=1))
    await async_session.commit()

    response = await admin_client.get("/admin/team-member/list")

    assert response.status_code == 200
    assert dweller.first_name in response.text
    assert "active" in response.text
    assert str(team) in response.text


async def test_verify_email_get_requires_confirmation_before_mutating(
    admin_client: AsyncClient, async_session: AsyncSession, superuser: User
) -> None:
    user = superuser
    user.email_verified = False
    async_session.add(user)
    await async_session.commit()
    response = await admin_client.get(f"/admin/user/action/verify-email?pks={user.id}")
    await async_session.refresh(user)
    assert user.email_verified is False
    assert response.status_code == 200
    assert 'method="post"' in response.text
    token = _csrf_token_from(response)
    response = await admin_client.post(
        "/admin/user/support", data={"operation": "verify-email", "pks": str(user.id), "csrf_token": token}
    )
    assert response.status_code == 303
    await async_session.refresh(user)
    assert user.email_verified is True


async def test_inactive_superuser_cannot_keep_admin_session(
    admin_client: AsyncClient, async_session: AsyncSession, superuser: User
) -> None:
    superuser.is_active = False
    async_session.add(superuser)
    await async_session.commit()
    response = await admin_client.get("/admin/")
    assert response.status_code in (302, 303)
    assert response.headers["location"].endswith("/admin/login")


async def test_admin_home_and_missing_operational_views_render(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/admin/")
    assert response.status_code == 200
    assert "Vault operations" in response.text
    assert "admin/theme.js" in response.text
    for identity in ("crafting-order", "vault-quest-completion-link", "pet", "o-auth-account"):
        response = await admin_client.get(f"/admin/{identity}/list")
        assert response.status_code == 200, identity


@pytest.mark.parametrize(
    "pks", ["", "not-a-uuid", "00000000-0000-4000-8000-000000000001,00000000-0000-4000-8000-000000000002"]
)
async def test_support_action_rejects_invalid_selection(admin_client: AsyncClient, pks: str) -> None:
    response = await admin_client.get("/admin/user/action/verify-email", params={"pks": pks})
    assert response.status_code == 400
    assert 'class="alert alert-danger"' in response.text


async def test_support_action_requires_csrf_and_disallows_cross_model_actions(
    admin_client: AsyncClient, async_session: AsyncSession, superuser: User
) -> None:
    superuser.email_verified = False
    async_session.add(superuser)
    await async_session.commit()
    response = await admin_client.post(
        "/admin/user/support", data={"operation": "verify-email", "pks": str(superuser.id)}
    )
    assert response.status_code == 403
    page = await admin_client.get(f"/admin/user/action/verify-email?pks={superuser.id}")
    assert str(superuser.email) in page.text
    response = await admin_client.post(
        "/admin/user/support",
        data={"operation": "pause", "pks": str(superuser.id), "csrf_token": _csrf_token_from(page)},
    )
    assert response.status_code == 400
    await async_session.refresh(superuser)
    assert superuser.email_verified is False


async def test_support_action_missing_record_returns_404(admin_client: AsyncClient) -> None:
    response = await admin_client.get(f"/admin/user/action/verify-email?pks={uuid4()}")
    assert response.status_code == 404
    assert "alert-danger" in response.text


async def test_vault_support_pause_resume_preserves_normal_game_state_transitions(
    admin_client: AsyncClient, async_session: AsyncSession, vault: Vault
) -> None:
    from app.crud.game_state import game_state_crud

    state = await game_state_crud.get_or_create(async_session, vault.id)
    for operation, expected in (("pause", True), ("resume", False)):
        page = await admin_client.get(f"/admin/vault/action/{operation}?pks={vault.id}")
        assert page.status_code == 200
        assert str(vault) in page.text
        await async_session.refresh(state)
        assert state.is_paused is not expected
        response = await admin_client.post(
            "/admin/vault/support",
            data={"operation": operation, "pks": str(vault.id), "csrf_token": _csrf_token_from(page)},
        )
        assert response.status_code == 303
        await async_session.refresh(state)
        assert state.is_paused is expected
        follow = await admin_client.get(response.headers["location"])
        assert follow.status_code == 200
        assert f"{operation.title()} vault completed." in follow.text


async def test_admin_cancels_training_without_stat_gain_and_rejects_repeat(
    admin_client: AsyncClient, async_session: AsyncSession, dweller: Dweller, room_in_vault: Any
) -> None:
    from app.core.enums import DwellerStatusEnum, RoomTypeEnum, SPECIALEnum
    from app.services.training_service import training_service

    room_in_vault.category = RoomTypeEnum.TRAINING
    room_in_vault.ability = SPECIALEnum.STRENGTH
    dweller.strength = 1
    dweller.status = DwellerStatusEnum.IDLE
    async_session.add_all([room_in_vault, dweller])
    await async_session.commit()
    training = await training_service.start_training(async_session, dweller.id, room_in_vault.id)
    page = await admin_client.get(f"/admin/training/action/cancel-training?pks={training.id}")
    assert page.status_code == 200
    assert dweller.display_name in page.text
    data = {"operation": "cancel-training", "pks": str(training.id), "csrf_token": _csrf_token_from(page)}
    response = await admin_client.post("/admin/training/support", data=data)
    assert response.status_code == 303
    await async_session.refresh(training)
    await async_session.refresh(dweller)
    assert training.status.value == "cancelled"
    assert dweller.status == DwellerStatusEnum.IDLE
    assert dweller.room_id is None
    assert dweller.strength == 1
    response = await admin_client.post("/admin/training/support", data=data)
    assert response.status_code == 400
    assert "alert-danger" in response.text


async def test_dweller_list_filters_and_sorting_affect_results(
    admin_client: AsyncClient, async_session: AsyncSession, dweller: Dweller
) -> None:
    from app.schemas.dweller import DwellerCreate
    from app.tests.factory.dwellers import create_fake_adult_dweller

    dweller.first_name = "AlphaVisible"
    dweller.is_dead = False
    async_session.add(dweller)
    other = await crud.dweller.create(
        async_session,
        DwellerCreate(**{**create_fake_adult_dweller(), "first_name": "ZuluHidden", "vault_id": dweller.vault_id}),
    )
    other.is_dead = True
    async_session.add(other)
    await async_session.commit()
    page = await admin_client.get("/admin/dweller/list", params={"is_dead": "false"})
    assert page.status_code == 200
    assert "AlphaVisible" in page.text
    assert "ZuluHidden" not in page.text
    page = await admin_client.get("/admin/dweller/list", params={"sortBy": "first_name", "sort": "desc"})
    assert page.status_code == 200
    assert page.text.index("ZuluHidden") < page.text.index("AlphaVisible")


@pytest.mark.parametrize("state", ["is_deleted", "is_superuser"])
async def test_revoked_admin_access_rejects_existing_session(
    admin_client: AsyncClient, async_session: AsyncSession, superuser: User, state: str
) -> None:
    setattr(superuser, state, state == "is_deleted")
    async_session.add(superuser)
    await async_session.commit()
    response = await admin_client.get("/admin/")
    assert response.status_code in (302, 303)
    assert response.headers["location"].endswith("/admin/login")


async def test_admin_recall_starts_return_without_granting_rewards(
    admin_client: AsyncClient, async_session: AsyncSession, dweller: Dweller, vault: Vault
) -> None:
    from app.core.enums import DwellerStatusEnum
    from app.services.exploration_service import exploration_service

    dweller.status = DwellerStatusEnum.IDLE
    dweller.health = dweller.max_health
    dweller.radiation = 0
    async_session.add(dweller)
    await async_session.commit()
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    caps_before = vault.bottle_caps
    page = await admin_client.get(f"/admin/exploration/action/recall?pks={exploration.id}")
    assert page.status_code == 200
    assert dweller.display_name in page.text
    data = {"operation": "recall", "pks": str(exploration.id), "csrf_token": _csrf_token_from(page)}
    response = await admin_client.post("/admin/exploration/support", data=data)
    assert response.status_code == 303
    await async_session.refresh(exploration)
    await async_session.refresh(dweller)
    await async_session.refresh(vault)
    assert exploration.status.value == "returning"
    assert exploration.recalled_early is True
    assert dweller.status == DwellerStatusEnum.EXPLORING
    assert vault.bottle_caps == caps_before
    response = await admin_client.post("/admin/exploration/support", data=data)
    assert response.status_code == 400


@pytest.mark.parametrize("identity", sorted(view.identity for view in admin._views if view.is_model))
async def test_all_admin_list_pages_render(admin_client: AsyncClient, identity: str) -> None:
    page = await admin_client.get(f"/admin/{identity}/list")
    assert page.status_code == 200, identity


async def test_operational_records_link_back_to_their_vault(
    admin_client: AsyncClient, async_session: AsyncSession, vault: Vault
) -> None:
    from app.crud.game_state import game_state_crud

    await game_state_crud.get_or_create(async_session, vault.id)
    page = await admin_client.get("/admin/game-state/list")
    assert page.status_code == 200
    assert f'href="https://testserver/admin/vault/details/{vault.id}"' in page.text


async def test_crafting_progress_is_readable_without_rounding_stored_value(
    admin_client: AsyncClient, async_session: AsyncSession, vault: Vault, room_in_vault: Any
) -> None:
    from datetime import datetime, timedelta

    from app.core.enums import RarityEnum
    from app.models.crafting_order import CraftingOrder

    progress = 0.0077497756788665875
    order = CraftingOrder(
        vault_id=vault.id,
        room_id=room_in_vault.id,
        item_name="Test workshop item",
        item_type="weapon",
        rarity=RarityEnum.COMMON,
        progress=progress,
        started_at=datetime.utcnow(),
        estimated_completion_at=datetime.utcnow() + timedelta(hours=1),
        required_stat="strength",
    )
    async_session.add(order)
    await async_session.commit()
    page = await admin_client.get("/admin/crafting-order/list")
    assert page.status_code == 200
    assert "0.8%" in page.text
    assert str(progress) not in page.text
    details = await admin_client.get(f"/admin/crafting-order/details/{order.id}")
    assert details.status_code == 200
    assert "0.8%" in details.text
    assert str(progress) not in details.text
    await async_session.refresh(order)
    assert order.progress == progress


@pytest.mark.parametrize(
    ("fields", "label"),
    [
        ({"name": "Scouting party"}, "Scouting party"),
        ({"hazard_team": HazardTeam.FIRE}, "Fire team"),
        ({"hazard_team": HazardTeam.RADIATION}, "Radiation team"),
        ({"quest_id": UUID("00000000-0000-4000-8000-000000000001")}, "Quest team"),
        ({"incident_id": UUID("00000000-0000-4000-8000-000000000001")}, "Incident team"),
        ({"exploration_id": UUID("00000000-0000-4000-8000-000000000001")}, "Exploration team"),
    ],
)
def test_team_display_label_does_not_dump_orm_fields(fields: dict, label: str) -> None:
    team = Team(vault_id=uuid4(), **fields)
    if team.name:
        assert str(team) == label
    else:
        assert str(team) == f"{label} ({str(team.id)[:8]})"
    assert "vault_id=" not in str(team)


async def test_incident_controls_paginate_without_preselecting_disabled_vaults(
    admin_client: AsyncClient, async_session: AsyncSession, vault: Vault
) -> None:
    others = [Vault(number=number, user_id=vault.user_id, incidents_disabled=True) for number in range(1, 53)]
    async_session.add_all(others)
    await async_session.commit()
    first = await admin_client.get("/admin/vault/incidents")
    second = await admin_client.get("/admin/vault/incidents?page=2")
    first_ids = set(re.findall(r'name="vault_id"\s+value="([^"]+)"', first.text))
    second_ids = set(re.findall(r'name="vault_id"\s+value="([^"]+)"', second.text))
    assert len(first_ids) == 50
    assert len(second_ids) == 3
    assert first_ids.isdisjoint(second_ids)
    assert "checked" not in first.text


async def test_incident_controls_reject_empty_selection_and_skip_deleted_vaults(
    admin_client: AsyncClient, async_session: AsyncSession, vault: Vault
) -> None:
    deleted = Vault(number=999, user_id=vault.user_id, is_deleted=True, incidents_disabled=False)
    async_session.add(deleted)
    await async_session.commit()
    page = await admin_client.get("/admin/vault/incidents")
    token = _csrf_token_from(page)
    response = await admin_client.post(
        "/admin/vault/incidents", data={"action": "disable", "scope": "selected", "csrf_token": token}
    )
    assert response.status_code == 400
    response = await admin_client.post(
        "/admin/vault/incidents", data={"action": "disable", "scope": "all", "csrf_token": token}
    )
    assert response.status_code == 303
    await async_session.refresh(vault)
    await async_session.refresh(deleted)
    assert vault.incidents_disabled is True
    assert deleted.incidents_disabled is False
    assert str(deleted.id) not in page.text


async def test_admin_promotes_user_only_after_post_confirmation(
    admin_client: AsyncClient, async_session: AsyncSession
) -> None:
    from app.schemas.user import UserCreate
    from app.tests.factory.users import create_fake_user

    credentials = create_fake_user()
    target = await crud.user.create(async_session, UserCreate(**credentials))
    assert target.is_superuser is False
    page = await admin_client.get(f"/admin/user/action/promote-superuser?pks={target.id}")
    assert page.status_code == 200
    await async_session.refresh(target)
    assert target.is_superuser is False
    response = await admin_client.post(
        "/admin/user/support", data={"operation": "promote-superuser", "pks": str(target.id)}
    )
    assert response.status_code == 403
    response = await admin_client.post(
        "/admin/user/support",
        data={"operation": "promote-superuser", "pks": str(target.id), "csrf_token": _csrf_token_from(page)},
    )
    assert response.status_code == 303
    await async_session.refresh(target)
    assert target.is_superuser is True

    login = await admin_client.post(
        "/admin/login", data={"username": credentials["email"], "password": credentials["password"]}
    )
    assert login.status_code == 302
    assert (await admin_client.get("/admin/")).status_code == 200


@pytest.mark.parametrize("existing_state", [False, True], ids=["missing-state", "existing-state"])
@pytest.mark.parametrize("first_admin_actor", [False, True])
async def test_admin_soft_deletes_user_and_pauses_vault_without_deleting_data(
    admin_client: AsyncClient,
    async_client: AsyncClient,
    async_session: AsyncSession,
    vault: Vault,
    existing_state: bool,
    first_admin_actor: bool,
) -> None:
    from app.core.security import create_access_token
    from app.crud.game_state import game_state_crud
    from app.schemas.user import UserCreate
    from app.tests.factory.users import create_fake_user

    if not first_admin_actor:
        credentials = create_fake_user()
        await crud.user.create(async_session, UserCreate(**credentials, is_superuser=True))
        await admin_client.post(
            "/admin/login", data={"username": credentials["email"], "password": credentials["password"]}
        )
    target = await crud.user.get(async_session, vault.user_id)
    headers = {"Authorization": f"Bearer {create_access_token(str(target.id))}"}
    assert (await async_client.get("/users/me", headers=headers)).status_code == 200
    if existing_state:
        await game_state_crud.get_or_create(async_session, vault.id)
    else:
        assert await game_state_crud.get_by_vault_id(async_session, vault.id) is None
    target.email_verification_token = "old-verification-link"
    target.password_reset_token = "old-reset-link"
    async_session.add(target)
    await async_session.commit()
    page = await admin_client.get(f"/admin/user/action/soft-delete?pks={target.id}")
    assert page.status_code == 200
    await async_session.refresh(target)
    assert target.is_deleted is False
    response = await admin_client.post(
        "/admin/user/support",
        data={"operation": "soft-delete", "pks": str(target.id), "csrf_token": _csrf_token_from(page)},
    )
    assert response.status_code == 303
    await async_session.refresh(target)
    await async_session.refresh(vault)
    state = await game_state_crud.get_by_vault_id(async_session, vault.id)
    assert state is not None
    assert target.is_deleted is True
    assert target.is_active is False
    assert target.deleted_at is not None
    assert target.email_verification_token is None
    assert target.password_reset_token is None
    assert state.is_paused is True
    assert state.paused_at is not None
    assert vault.is_deleted is False
    await async_session.refresh(target, attribute_names=["profile"])
    assert target.profile is not None
    assert await crud.user.get_by_email(async_session, target.email) is None

    assert (await async_client.get("/users/me", headers=headers)).status_code == 404


async def test_admin_cannot_soft_delete_current_account(
    admin_client: AsyncClient, async_session: AsyncSession, superuser: User
) -> None:
    page = await admin_client.get(f"/admin/user/action/soft-delete?pks={superuser.id}")
    assert page.status_code == 200
    response = await admin_client.post(
        "/admin/user/support",
        data={"operation": "soft-delete", "pks": str(superuser.id), "csrf_token": _csrf_token_from(page)},
    )
    assert response.status_code == 400
    await async_session.refresh(superuser)
    assert superuser.is_deleted is False
    assert (await admin_client.get("/admin/")).status_code == 200


def test_quest_requirement_and_reward_labels_are_concise() -> None:
    from app.models.quest_requirement import QuestRequirement, RequirementType
    from app.models.quest_reward import QuestReward, RewardType

    requirement = QuestRequirement(
        quest_id=uuid4(), requirement_type=RequirementType.LEVEL, requirement_data={"level": 46}
    )
    reward = QuestReward(quest_id=uuid4(), reward_type=RewardType.CAPS, reward_data={"amount": 200})
    assert str(requirement) == "Level (level: 46)"
    assert str(reward) == "Caps (amount: 200)"
    assert "quest_id=" not in str(requirement)
    assert "quest_id=" not in str(reward)


async def test_quest_related_labels_and_links_render(admin_client: AsyncClient, async_session: AsyncSession) -> None:
    from app.models.quest_requirement import QuestRequirement, RequirementType
    from app.models.quest_reward import QuestReward, RewardType
    from app.schemas.quest import QuestCreate

    quest = await crud.quest_crud.create(
        async_session,
        QuestCreate(
            title="Admin display quest",
            short_description="Test display",
            long_description="Test display details",
            requirements="Level 46",
            rewards="200 caps",
        ),
    )
    assert str(quest) == "Admin display quest"
    requirement = QuestRequirement(
        quest_id=quest.id, requirement_type=RequirementType.LEVEL, requirement_data={"level": 46}
    )
    reward = QuestReward(quest_id=quest.id, reward_type=RewardType.CAPS, reward_data={"amount": 200})
    async_session.add_all([requirement, reward])
    await async_session.commit()
    page = await admin_client.get(f"/admin/quest/details/{quest.id}")
    assert page.status_code == 200
    assert "Level (level: 46)" in page.text
    assert "Caps (amount: 200)" in page.text
    for identity, record in (("quest-requirement", requirement), ("quest-reward", reward)):
        assert f"/admin/{identity}/details/{record.id}" in page.text
        details = await admin_client.get(f"/admin/{identity}/details/{record.id}")
        assert details.status_code == 200
        assert "Admin display quest" in details.text


async def test_sent_notification_labels_do_not_dump_message_or_user_fields(
    admin_client: AsyncClient, async_session: AsyncSession, dweller: Dweller, vault: Vault
) -> None:
    from app.models.notification import Notification, NotificationType

    notice = Notification(
        user_id=vault.user_id,
        vault_id=vault.id,
        from_dweller_id=dweller.id,
        notification_type=NotificationType.LEVEL_UP,
        title="Ada reached level 2",
        message="Full private message body",
    )
    async_session.add(notice)
    await async_session.commit()
    assert str(notice) == "Ada reached level 2 (level up)"
    page = await admin_client.get(f"/admin/dweller/details/{dweller.id}")
    assert page.status_code == 200
    assert str(notice) in page.text
    assert notice.message not in page.text
    assert f"/admin/notification/details/{notice.id}" in page.text


async def test_profile_metadata_remains_editable_without_exposing_owner_or_counters(
    admin_client: AsyncClient, async_session: AsyncSession, superuser: User
) -> None:
    await async_session.refresh(superuser, attribute_names=["profile"])
    profile = superuser.profile
    previous_caps = profile.total_caps_earned
    page = await admin_client.get(f"/admin/user-profile/edit/{profile.id}")
    assert page.status_code == 200
    assert 'name="bio"' in page.text
    assert 'name="avatar_url"' in page.text
    assert 'name="total_caps_earned"' not in page.text
    assert 'name="user"' not in page.text
    response = await admin_client.post(
        f"/admin/user-profile/edit/{profile.id}",
        data={"bio": "Updated support bio", "avatar_url": "", "total_caps_earned": "999999"},
    )
    assert response.status_code == 302
    await async_session.refresh(profile)
    assert profile.bio == "Updated support bio"
    assert profile.user_id == superuser.id
    assert profile.total_caps_earned == previous_caps


@pytest.mark.parametrize("existing_state", [False, True])
@pytest.mark.parametrize("first_admin_actor", [False, True])
async def test_deactivate_and_reactivate_preserve_account_and_pause_vaults(
    admin_client: AsyncClient,
    async_session: AsyncSession,
    async_client: AsyncClient,
    vault: Vault,
    existing_state: bool,
    first_admin_actor: bool,
) -> None:
    from app.core.security import create_access_token
    from app.crud.game_state import game_state_crud
    from app.schemas.user import UserCreate
    from app.tests.factory.users import create_fake_user

    if not first_admin_actor:
        credentials = create_fake_user()
        await crud.user.create(async_session, UserCreate(**credentials, is_superuser=True))
        await admin_client.post(
            "/admin/login", data={"username": credentials["email"], "password": credentials["password"]}
        )
    target = await crud.user.get(async_session, vault.user_id)
    headers = {"Authorization": f"Bearer {create_access_token(str(target.id))}"}
    if existing_state:
        await game_state_crud.get_or_create(async_session, vault.id)
    target.email_verification_token = "old-verification-link"
    target.password_reset_token = "old-reset-link"
    async_session.add(target)
    await async_session.commit()

    page = await admin_client.get(f"/admin/user/action/deactivate?pks={target.id}")
    assert page.status_code == 200
    await async_session.refresh(target)
    assert target.is_active is True
    blocked = await admin_client.post("/admin/user/support", data={"operation": "deactivate", "pks": str(target.id)})
    assert blocked.status_code == 403
    response = await admin_client.post(
        "/admin/user/support",
        data={"operation": "deactivate", "pks": str(target.id), "csrf_token": _csrf_token_from(page)},
    )
    assert response.status_code == 303
    await async_session.refresh(target)
    assert target.is_active is False
    assert target.is_deleted is False
    assert target.deleted_at is None
    assert target.email_verification_token is None
    assert target.password_reset_token is None
    assert await crud.user.get_by_email(async_session, target.email) is not None
    state = await game_state_crud.get_by_vault_id(async_session, vault.id)
    assert state is not None
    assert state.is_paused
    assert (await async_client.get("/users/me", headers=headers)).status_code == 403

    page = await admin_client.get(f"/admin/user/action/reactivate?pks={target.id}")
    assert page.status_code == 200
    response = await admin_client.post(
        "/admin/user/support",
        data={"operation": "reactivate", "pks": str(target.id), "csrf_token": _csrf_token_from(page)},
    )
    assert response.status_code == 303
    await async_session.refresh(target)
    assert target.is_active is True
    assert target.is_deleted is False
    await async_session.refresh(state)
    assert state.is_paused is True
    assert (await async_client.get("/users/me", headers=headers)).status_code == 200


async def test_admin_cannot_deactivate_current_account(admin_client, async_session, superuser):
    page = await admin_client.get(f"/admin/user/action/deactivate?pks={superuser.id}")
    assert page.status_code == 200
    response = await admin_client.post(
        "/admin/user/support",
        data={"operation": "deactivate", "pks": str(superuser.id), "csrf_token": _csrf_token_from(page)},
    )
    assert response.status_code == 400
    await async_session.refresh(superuser)
    assert superuser.is_active is True
    assert (await admin_client.get("/admin/")).status_code == 200


async def test_reactivate_does_not_restore_a_soft_deleted_account(admin_client, async_session, vault):
    target = await crud.user.get(async_session, vault.user_id)
    page = await admin_client.get(f"/admin/user/action/reactivate?pks={target.id}")
    assert page.status_code == 200
    target.soft_delete()
    target.is_active = False
    async_session.add(target)
    await async_session.commit()
    response = await admin_client.post(
        "/admin/user/support",
        data={"operation": "reactivate", "pks": str(target.id), "csrf_token": _csrf_token_from(page)},
    )
    assert response.status_code == 404
    await async_session.refresh(target)
    assert target.is_active is False
    assert target.is_deleted is True


async def test_first_superuser_demotes_only_after_confirmation_and_revokes_admin_session(
    admin_client: AsyncClient, async_session: AsyncSession, async_client: AsyncClient
) -> None:
    from app.core.security import create_access_token
    from app.schemas.user import UserCreate
    from app.tests.factory.users import create_fake_user

    credentials = create_fake_user()
    target = await crud.user.create(async_session, UserCreate(**credentials, is_superuser=True))
    headers = {"Authorization": f"Bearer {create_access_token(str(target.id))}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as target_client:
        login = await target_client.post(
            "/admin/login", data={"username": credentials["email"], "password": credentials["password"]}
        )
        assert login.status_code == 302
        assert (await target_client.get("/admin/")).status_code == 200
        page = await admin_client.get(f"/admin/user/action/demote-superuser?pks={target.id}")
        assert page.status_code == 200
        await async_session.refresh(target)
        assert target.is_superuser is True
        assert (
            await admin_client.post(
                "/admin/user/support", data={"operation": "demote-superuser", "pks": str(target.id)}
            )
        ).status_code == 403
        response = await admin_client.post(
            "/admin/user/support",
            data={"operation": "demote-superuser", "pks": str(target.id), "csrf_token": _csrf_token_from(page)},
        )
        assert response.status_code == 303
        await async_session.refresh(target)
        assert target.is_superuser is False
        assert target.is_active is True
        assert target.is_deleted is False
        assert (await target_client.get("/admin/")).status_code == 302
        assert (await async_client.get("/users/me", headers=headers)).status_code == 200


@pytest.mark.parametrize(
    "operation", ["promote-superuser", "demote-superuser", "deactivate", "reactivate", "soft-delete"]
)
async def test_other_admin_cannot_change_first_superuser_or_bypass_action_permissions(
    admin_client, async_session, superuser, operation
):
    from app.schemas.user import UserCreate
    from app.tests.factory.users import create_fake_user

    credentials = create_fake_user()
    await crud.user.create(async_session, UserCreate(**credentials, is_superuser=True))
    target = await crud.user.create(async_session, UserCreate(**create_fake_user()))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as other_client:
        await other_client.post(
            "/admin/login", data={"username": credentials["email"], "password": credentials["password"]}
        )
        listing = await other_client.get("/admin/user/list")
        assert listing.status_code == 200
        assert "/action/promote-superuser" not in listing.text
        assert "/action/demote-superuser" not in listing.text
        # A regular-user support operation remains available and supplies a valid token.
        page = await other_client.get(f"/admin/user/action/verify-email?pks={target.id}")
        assert page.status_code == 200
        assert (await other_client.get(f"/admin/user/action/{operation}?pks={superuser.id}")).status_code == 403
        response = await other_client.post(
            "/admin/user/support",
            data={"operation": operation, "pks": str(superuser.id), "csrf_token": _csrf_token_from(page)},
        )
        assert response.status_code == 403
        if operation in {"promote-superuser", "demote-superuser"}:
            response = await other_client.post(
                "/admin/user/support",
                data={"operation": operation, "pks": str(target.id), "csrf_token": _csrf_token_from(page)},
            )
            assert response.status_code == 403
    await async_session.refresh(superuser)
    assert superuser.is_superuser
    assert superuser.is_active
    assert not superuser.is_deleted


async def test_first_superuser_cannot_demote_itself(admin_client, async_session, superuser):
    page = await admin_client.get(f"/admin/user/action/demote-superuser?pks={superuser.id}")
    assert page.status_code == 200
    response = await admin_client.post(
        "/admin/user/support",
        data={"operation": "demote-superuser", "pks": str(superuser.id), "csrf_token": _csrf_token_from(page)},
    )
    assert response.status_code == 400
    await async_session.refresh(superuser)
    assert superuser.is_superuser is True


async def test_first_superuser_keeps_authority_after_changing_email(admin_client, async_session, superuser):
    from app.schemas.user import UserCreate
    from app.tests.factory.users import create_fake_user

    superuser.email = create_fake_user()["email"]
    async_session.add(superuser)
    await async_session.commit()
    target = await crud.user.create(async_session, UserCreate(**create_fake_user()))
    page = await admin_client.get(f"/admin/user/action/promote-superuser?pks={target.id}")
    assert page.status_code == 200
    response = await admin_client.post(
        "/admin/user/support",
        data={"operation": "promote-superuser", "pks": str(target.id), "csrf_token": _csrf_token_from(page)},
    )
    assert response.status_code == 303
    await async_session.refresh(target)
    assert target.is_superuser is True
    assert target.is_first_superuser is False
    assert superuser.is_first_superuser is True


def test_first_superuser_marker_is_not_client_writable():
    from app.schemas.user import UserCreate, UserRead, UserUpdate

    for schema in (UserCreate, UserRead, UserUpdate):
        assert "is_first_superuser" not in schema.model_fields


@pytest.mark.parametrize("first_admin_actor", [False, True])
@pytest.mark.parametrize("admin_target", [False, True])
async def test_profile_edit_uses_same_administrator_account_permissions(
    admin_client, async_session, superuser, first_admin_actor, admin_target
):
    from app.schemas.user import UserCreate
    from app.tests.factory.users import create_fake_user

    target = superuser if admin_target else await crud.user.create(async_session, UserCreate(**create_fake_user()))
    await async_session.refresh(target, attribute_names=["profile"])
    profile = target.profile
    original_bio = profile.bio
    if not first_admin_actor:
        credentials = create_fake_user()
        await crud.user.create(async_session, UserCreate(**credentials, is_superuser=True))
        await admin_client.post(
            "/admin/login", data={"username": credentials["email"], "password": credentials["password"]}
        )
    url = f"/admin/user-profile/edit/{profile.id}"
    allowed = first_admin_actor or not admin_target
    assert (await admin_client.get(url)).status_code == (200 if allowed else 403)
    response = await admin_client.post(url, data={"bio": "Permission-checked edit", "avatar_url": ""})
    assert response.status_code == (302 if allowed else 403)
    await async_session.refresh(profile)
    assert profile.bio == ("Permission-checked edit" if allowed else original_bio)


@pytest.mark.parametrize("method", ["GET", "POST"])
async def test_editing_missing_profile_keeps_not_found_response(admin_client, method):
    response = await admin_client.request(method, f"/admin/user-profile/edit/{uuid4()}")
    assert response.status_code == 404


async def _merge_user(async_session: AsyncSession, label: str) -> User:
    suffix = uuid4().hex[:10]
    return await crud.user.create(
        async_session,
        UserCreate(username=f"{label}{suffix}", email=f"{label}{suffix}@example.com", password="Secret123!"),
    )


def _merge_form(source: User, target: User, token: str, action: str = "preview") -> dict[str, str]:
    return {
        "csrf_token": token,
        "action": action,
        "source": str(source.id),
        "target": str(target.id),
        "reason": "duplicate account",
    }


def test_merge_accounts_admin_views_are_configured() -> None:
    assert MergeAccountsAdmin.name == "Merge accounts"
    assert MergeAccountsAdmin.category == "Accounts"
    assert MergeAccountsAdmin.page._exposed is True
    assert set(MergeAccountsAdmin.page._methods) == {"GET", "POST"}
    assert AccountMergeAdmin.category == "Accounts"
    assert AccountMergeAdmin.can_create is False
    assert AccountMergeAdmin.can_edit is False
    assert AccountMergeAdmin.can_delete is False
    assert AccountMergeAdmin.can_export is False


async def test_merge_accounts_page_renders_form_and_csrf(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/admin/merge-accounts")
    assert response.status_code == 200
    assert "Merge accounts" in response.text
    assert 'name="csrf_token"' in response.text
    assert 'name="source"' in response.text
    assert 'name="action" value="preview"' in response.text


async def test_merge_accounts_requires_admin_login() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as anonymous:
        response = await anonymous.get("/admin/merge-accounts")
    assert response.status_code in (302, 303)
    assert "/admin/login" in response.headers["location"]


async def test_merge_accounts_preview_requires_csrf(admin_client: AsyncClient) -> None:
    source = uuid4()
    target = uuid4()
    response = await admin_client.post(
        "/admin/merge-accounts",
        data={"action": "preview", "source": str(source), "target": str(target), "reason": "duplicate"},
    )
    assert response.status_code == 403

    response = await admin_client.post(
        "/admin/merge-accounts",
        data={
            "action": "preview",
            "source": str(source),
            "target": str(target),
            "reason": "duplicate",
            "csrf_token": "bad",
        },
    )
    assert response.status_code == 403


async def test_merge_accounts_preview_does_not_mutate(admin_client: AsyncClient, async_session: AsyncSession) -> None:
    source = await _merge_user(async_session, "mergesrc")
    target = await _merge_user(async_session, "mergetgt")
    async_session.add(Vault(user_id=source.id, number=random_vault_number()))
    await async_session.commit()
    page = await admin_client.get("/admin/merge-accounts")
    response = await admin_client.post(
        "/admin/merge-accounts", data=_merge_form(source, target, _csrf_token_from(page))
    )

    assert response.status_code == 200
    assert "Preview" in response.text
    assert "vaults" in response.text
    assert 'name="action" value="apply"' in response.text
    await async_session.refresh(source)
    assert source.is_deleted is False
    assert await crud.account_merge.get_by_source(async_session, source.id) is None
    assert await crud.vault.count_by_user(async_session, source.id) == 1


async def test_merge_accounts_apply_moves_source_and_writes_audit(
    admin_client: AsyncClient, async_session: AsyncSession, superuser: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = await _merge_user(async_session, "mergesrc")
    target = await _merge_user(async_session, "mergetgt")
    source_id = source.id
    target_id = target.id
    source_username = source.username
    async_session.add(Vault(user_id=source_id, number=random_vault_number()))
    await async_session.commit()

    fake_redis = AsyncMock()
    fake_redis.delete = AsyncMock()
    fake_redis.aclose = AsyncMock()
    monkeypatch.setattr(admin_actions.Redis, "from_url", lambda *args, **kwargs: fake_redis)

    page = await admin_client.get("/admin/merge-accounts")
    response = await admin_client.post(
        "/admin/merge-accounts", data=_merge_form(source, target, _csrf_token_from(page), action="apply")
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert "/admin/account-merge/list" in location
    assert (await admin_client.get(location)).status_code == 200

    await async_session.refresh(source)
    assert source.is_deleted is True
    assert source.is_active is False
    assert await crud.vault.count_by_user(async_session, source_id) == 0
    assert await crud.vault.count_by_user(async_session, target_id) == 1
    audit = await crud.account_merge.get_by_source(async_session, source_id)
    assert audit is not None
    assert audit.target_user_id == target_id
    assert audit.actor_user_id == superuser.id
    assert fake_redis.delete.await_count == 1
    assert fake_redis.aclose.await_count == 1
    assert source_username in (await admin_client.get(location)).text


async def test_merge_accounts_rejects_oauth_provider_conflict(
    admin_client: AsyncClient, async_session: AsyncSession
) -> None:
    source = await _merge_user(async_session, "mergesrc")
    target = await _merge_user(async_session, "mergetgt")
    async_session.add_all(
        [
            OAuthAccount(provider="google", provider_user_id=uuid4().hex, user_id=source.id),
            OAuthAccount(provider="google", provider_user_id=uuid4().hex, user_id=target.id),
        ]
    )
    await async_session.commit()
    page = await admin_client.get("/admin/merge-accounts")

    response = await admin_client.post(
        "/admin/merge-accounts", data=_merge_form(source, target, _csrf_token_from(page))
    )

    assert response.status_code == 200
    assert "google" in response.text
    assert 'name="action" value="apply"' not in response.text
    await async_session.refresh(source)
    assert source.is_deleted is False
    assert await crud.account_merge.get_by_source(async_session, source.id) is None


async def test_account_merge_audit_list_is_read_only(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/admin/account-merge/list")
    assert response.status_code == 200
