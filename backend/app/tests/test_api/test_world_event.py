"""World event read and claim endpoints: ownership, empty state, and claim failures."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.api.deps import get_current_active_user
from app.core.enums import WorldEventStatus
from app.core.game_config import game_config
from app.models.user import User
from app.models.vault import Vault
from app.models.world_event import WorldEvent, WorldEventParticipation
from app.schemas.user import UserCreate
from app.schemas.world_event import WorldEventClaimRead, WorldEventRead
from app.tests.factory.users import create_fake_user
from main import app

REWARD = [{"reward_type": "caps", "amount": 50}]


async def _add_event(
    async_session: AsyncSession,
    *,
    status: WorldEventStatus = WorldEventStatus.ACTIVE,
    progress_amount: int = 40,
    personal_min: int = 10,
) -> WorldEvent:
    now = datetime.now(UTC)
    event = WorldEvent(
        kind="wasteland_push",
        title="Push the wastes",
        description="Collect for everyone.",
        target_amount=100,
        progress_amount=progress_amount,
        personal_min=personal_min,
        reward=REWARD,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=1),
        status=status,
    )
    async_session.add(event)
    await async_session.commit()
    return event


async def _add_participation(
    async_session: AsyncSession, event: WorldEvent, vault: Vault, contribution: int
) -> WorldEventParticipation:
    participation = WorldEventParticipation(world_event_id=event.id, vault_id=vault.id, contribution=contribution)
    async_session.add(participation)
    await async_session.commit()
    return participation


async def _claim(async_client: AsyncClient, vault: Vault, *, status: int = 400, detail: str | None = None):
    response = await async_client.post(f"/vaults/{vault.id}/world-event/claim")
    assert response.status_code == status, response.text
    if detail is not None:
        assert response.json()["detail"] == detail
    return response


@pytest.fixture(autouse=True)
def _world_events_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """The feature ships dark; these tests exercise the enabled surface."""
    monkeypatch.setattr(game_config.features, "world_events", True)


@pytest_asyncio.fixture(name="owner")
async def owner_fixture(user: User) -> AsyncGenerator[User]:
    app.dependency_overrides[get_current_active_user] = lambda: user
    try:
        yield user
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)


async def test_owner_reads_progress_and_own_standing(
    async_client: AsyncClient, async_session: AsyncSession, owner: User, vault: Vault
) -> None:
    event = await _add_event(async_session)
    await _add_participation(async_session, event, vault, 25)

    response = await async_client.get(f"/vaults/{vault.id}/world-event")

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == set(WorldEventRead.model_fields)
    assert body["event_id"] == str(event.id)
    assert body["kind"] == "wasteland_push"
    assert body["title"] == "Push the wastes"
    assert body["target_amount"] == 100
    assert body["progress_amount"] == 40
    assert body["participant_count"] == 1
    assert body["contribution"] == 25
    assert body["personal_min"] == 10
    assert body["can_claim"] is False
    assert body["status"] == WorldEventStatus.ACTIVE.value
    assert body["starts_at"] is not None
    assert body["ends_at"] is not None
    assert body["reward"] == REWARD


async def test_foreign_vault_is_forbidden(async_client: AsyncClient, async_session: AsyncSession, vault: Vault) -> None:
    await _add_event(async_session)
    foreign_user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    app.dependency_overrides[get_current_active_user] = lambda: foreign_user
    try:
        response = await async_client.get(f"/vaults/{vault.id}/world-event")
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)

    assert response.status_code == 403
    assert response.json()["detail"] == "The user doesn't have enough privileges"


async def test_no_event_yields_well_formed_empty_payload(async_client: AsyncClient, owner: User, vault: Vault) -> None:
    response = await async_client.get(f"/vaults/{vault.id}/world-event")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "event_id": None,
        "kind": None,
        "title": None,
        "description": None,
        "target_amount": 0,
        "progress_amount": 0,
        "participant_count": 0,
        "contribution": 0,
        "personal_min": 0,
        "can_claim": False,
        "status": None,
        "starts_at": None,
        "ends_at": None,
        "extended_at": None,
        "reward": [],
    }


@pytest.mark.parametrize("join_active", [False, True], ids=["no-participation", "only-active-participation"])
async def test_claim_rejected_while_ineligible(
    async_client: AsyncClient, async_session: AsyncSession, owner: User, vault: Vault, join_active: bool
) -> None:
    await _add_event(async_session, status=WorldEventStatus.COMPLETED)
    if join_active:
        # Contributing to a still-running event is not enough: the only completed event on record
        # is the one this vault never joined.
        active = await _add_event(async_session)
        await _add_participation(async_session, active, vault, 100)

    await _claim(async_client, vault, detail="Your vault took no part in this world event.")


async def test_claim_rejected_before_any_event_completes(
    async_client: AsyncClient, async_session: AsyncSession, owner: User, vault: Vault
) -> None:
    active = await _add_event(async_session)
    await _add_participation(async_session, active, vault, 90)

    await _claim(async_client, vault, detail="The world event is not complete yet.")


async def test_claim_still_pays_a_completed_event_after_the_next_one_activates(
    async_client: AsyncClient, async_session: AsyncSession, owner: User, vault: Vault
) -> None:
    """Rotation must not strand an unclaimed reward: claims target the finished event."""
    finished = await _add_event(async_session, status=WorldEventStatus.COMPLETED)
    await _add_participation(async_session, finished, vault, 25)
    await _add_event(async_session)  # next event is now ACTIVE
    vault.bottle_caps = 500
    async_session.add(vault)
    await async_session.commit()

    response = await _claim(async_client, vault, status=200)

    assert response.json()["event_id"] == str(finished.id)
    await async_session.refresh(vault)
    assert vault.bottle_caps == 550


async def test_endpoints_are_hidden_while_the_flag_is_off(
    async_client: AsyncClient,
    async_session: AsyncSession,
    owner: User,
    vault: Vault,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(game_config.features, "world_events", False)
    await _add_event(async_session)

    read = await async_client.get(f"/vaults/{vault.id}/world-event")
    claim = await async_client.post(f"/vaults/{vault.id}/world-event/claim")

    assert read.status_code == 404
    assert claim.status_code == 404


async def test_claim_pays_rewards_once(
    async_client: AsyncClient, async_session: AsyncSession, owner: User, vault: Vault
) -> None:
    event = await _add_event(async_session, status=WorldEventStatus.COMPLETED)
    participation = await _add_participation(async_session, event, vault, 25)
    vault.bottle_caps = 1_000
    async_session.add(vault)
    await async_session.commit()
    caps_before = vault.bottle_caps

    response = await _claim(async_client, vault, status=200)

    body = response.json()
    assert set(body) == set(WorldEventClaimRead.model_fields)
    assert body["event_id"] == str(event.id)
    assert body["claimed"] is True
    assert body["contribution"] == 25
    await async_session.refresh(vault)
    await async_session.refresh(participation)
    assert vault.bottle_caps - caps_before == 50
    assert participation.reward_claimed_at is not None

    await _claim(async_client, vault, status=409)
    await async_session.refresh(vault)
    assert vault.bottle_caps == caps_before + 50
