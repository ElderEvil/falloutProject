"""World event read and claim endpoints: ownership, empty state, and claim failures."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.api.deps import get_current_active_user
from app.core.enums import WorldEventStatus
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


async def test_claim_rejected_while_ineligible(
    async_client: AsyncClient, async_session: AsyncSession, owner: User, vault: Vault
) -> None:
    completed = await _add_event(async_session, status=WorldEventStatus.COMPLETED)
    response = await async_client.post(f"/vaults/{vault.id}/world-event/claim")
    assert response.status_code == 400
    assert response.json()["detail"] == "Your vault took no part in this world event."

    active = await _add_event(async_session)
    await _add_participation(async_session, active, vault, completed.target_amount)
    response = await async_client.post(f"/vaults/{vault.id}/world-event/claim")
    assert response.status_code == 400
    assert response.json()["detail"] == "The world event is not complete yet."


async def test_claim_pays_rewards_once(
    async_client: AsyncClient, async_session: AsyncSession, owner: User, vault: Vault
) -> None:
    event = await _add_event(async_session, status=WorldEventStatus.COMPLETED)
    participation = await _add_participation(async_session, event, vault, 25)
    vault.bottle_caps = 1_000
    async_session.add(vault)
    await async_session.commit()
    caps_before = vault.bottle_caps

    response = await async_client.post(f"/vaults/{vault.id}/world-event/claim")

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == set(WorldEventClaimRead.model_fields)
    assert body["event_id"] == str(event.id)
    assert body["claimed"] is True
    assert body["contribution"] == 25
    await async_session.refresh(vault)
    await async_session.refresh(participation)
    assert vault.bottle_caps - caps_before == 50
    assert participation.reward_claimed_at is not None

    repeat = await async_client.post(f"/vaults/{vault.id}/world-event/claim")

    assert repeat.status_code == 409
    await async_session.refresh(vault)
    assert vault.bottle_caps == caps_before + 50
