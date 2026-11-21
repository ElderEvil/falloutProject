"""World event service: contributions, lifecycle advances, reads and one-time claims."""

from datetime import timedelta

import pytest
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.enums import WorldEventStatus
from app.models.vault import Vault
from app.models.world_event import WorldEvent, WorldEventParticipation
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.world_event_service import world_event_service
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ResourceConflictException, ValidationException
from app.utils.time import utcnow

KIND = "migration"


async def _create_vault(async_session: AsyncSession) -> Vault:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    return await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))


async def _create_event(
    async_session: AsyncSession,
    *,
    status: WorldEventStatus = WorldEventStatus.ACTIVE,
    starts_at=None,
    ends_at=None,
    target_amount: int = 100,
    personal_min: int = 10,
    kind: str = KIND,
    reward: list[dict] | None = None,
) -> WorldEvent:
    now = utcnow()
    event = WorldEvent(
        kind=kind,
        title="Migration surge",
        description="Creatures are on the move.",
        target_amount=target_amount,
        personal_min=personal_min,
        reward=reward or [],
        starts_at=starts_at or now - timedelta(hours=1),
        ends_at=ends_at or now + timedelta(hours=1),
        status=status,
    )
    async_session.add(event)
    await async_session.commit()
    await async_session.refresh(event)
    return event


async def _create_participation(
    async_session: AsyncSession, event: WorldEvent, vault_id, contribution: int
) -> WorldEventParticipation:
    participation = WorldEventParticipation(world_event_id=event.id, vault_id=vault_id, contribution=contribution)
    async_session.add(participation)
    await async_session.commit()
    await async_session.refresh(participation)
    return participation


async def _participation_count(async_session: AsyncSession) -> int:
    return int((await async_session.execute(select(func.count()).select_from(WorldEventParticipation))).scalar_one())


# --- contributions -----------------------------------------------------------


async def test_contribution_credits_active_event(async_session: AsyncSession, vault: Vault) -> None:
    event = await _create_event(async_session)

    await world_event_service.record_contribution(async_session, vault.id, 7, kind=KIND)
    await async_session.commit()
    await async_session.refresh(event)

    participation = await crud.world_event.get_participation(async_session, event.id, vault.id)
    assert participation is not None
    assert participation.contribution == 7
    assert event.progress_amount == 7


async def test_contribution_noop_without_event(async_session: AsyncSession, vault: Vault) -> None:
    await world_event_service.record_contribution(async_session, vault.id, 7, kind=KIND)
    await async_session.commit()

    assert await _participation_count(async_session) == 0


async def test_contribution_noop_for_non_positive_amount(async_session: AsyncSession, vault: Vault) -> None:
    event = await _create_event(async_session)

    await world_event_service.record_contribution(async_session, vault.id, 0, kind=KIND)
    await world_event_service.record_contribution(async_session, vault.id, -5, kind=KIND)
    await async_session.commit()
    await async_session.refresh(event)

    assert await _participation_count(async_session) == 0
    assert event.progress_amount == 0


async def test_contribution_ignores_non_active_event(async_session: AsyncSession, vault: Vault) -> None:
    event = await _create_event(async_session, status=WorldEventStatus.SCHEDULED)

    await world_event_service.record_contribution(async_session, vault.id, 7, kind=KIND)
    await async_session.commit()
    await async_session.refresh(event)

    assert await _participation_count(async_session) == 0
    assert event.progress_amount == 0


async def test_progress_and_contribution_move_together(async_session: AsyncSession, vault: Vault) -> None:
    event = await _create_event(async_session)

    await world_event_service.record_contribution(async_session, vault.id, 5, kind=KIND)
    await world_event_service.record_contribution(async_session, vault.id, 7, kind=KIND)
    await async_session.commit()
    await async_session.refresh(event)

    participation = await crud.world_event.get_participation(async_session, event.id, vault.id)
    assert participation is not None
    assert participation.contribution == 12
    assert event.progress_amount == 12


async def test_two_vaults_first_contribution_both_land(async_session: AsyncSession, vault: Vault) -> None:
    event = await _create_event(async_session)
    other_vault = await _create_vault(async_session)

    await world_event_service.record_contribution(async_session, vault.id, 4, kind=KIND)
    await world_event_service.record_contribution(async_session, other_vault.id, 6, kind=KIND)
    await async_session.commit()
    await async_session.refresh(event)

    assert await _participation_count(async_session) == 2
    assert await crud.world_event.totals(async_session, event.id) == (2, 10)
    assert event.progress_amount == 10


# --- lifecycle ---------------------------------------------------------------


async def test_advance_activates_due_scheduled_event(async_session: AsyncSession) -> None:
    now = utcnow()
    event = await _create_event(async_session, status=WorldEventStatus.SCHEDULED, starts_at=now - timedelta(minutes=5))

    result = await world_event_service.advance(async_session)
    await async_session.refresh(event)

    assert result["action"] == "activated"
    assert result["event_id"] == event.id
    assert event.status == WorldEventStatus.ACTIVE


async def test_advance_refuses_second_active_event(async_session: AsyncSession) -> None:
    now = utcnow()
    active = await _create_event(async_session, starts_at=now - timedelta(hours=2))
    scheduled = await _create_event(
        async_session, status=WorldEventStatus.SCHEDULED, starts_at=now - timedelta(minutes=5)
    )

    result = await world_event_service.advance(async_session)
    await async_session.refresh(active)
    await async_session.refresh(scheduled)

    assert result["action"] is None
    assert active.status == WorldEventStatus.ACTIVE
    assert scheduled.status == WorldEventStatus.SCHEDULED


async def test_advance_completes_at_target(async_session: AsyncSession) -> None:
    event = await _create_event(async_session, target_amount=10)
    event.progress_amount = 10
    async_session.add(event)
    await async_session.commit()

    result = await world_event_service.advance(async_session)
    await async_session.refresh(event)

    assert result["action"] == "completed"
    assert event.status == WorldEventStatus.COMPLETED


async def test_advance_extends_once_then_expires(async_session: AsyncSession) -> None:
    now = utcnow()
    event = await _create_event(
        async_session,
        starts_at=now - timedelta(hours=2),
        ends_at=now - timedelta(minutes=1),
        target_amount=100,
    )

    first = await world_event_service.advance(async_session)
    await async_session.refresh(event)
    assert first["action"] == "extended"
    assert event.status == WorldEventStatus.ACTIVE
    assert event.extended_at is not None
    extended_ends_at = event.ends_at
    assert extended_ends_at > now

    # Past the extension window: the same event can no longer be extended again.
    event.ends_at = utcnow() - timedelta(minutes=1)
    async_session.add(event)
    await async_session.commit()

    second = await world_event_service.advance(async_session)
    await async_session.refresh(event)
    assert second["action"] == "expired"
    assert event.status == WorldEventStatus.EXPIRED
    assert event.extended_at is not None


# --- claim -------------------------------------------------------------------


async def _completed_event_with_participation(
    async_session: AsyncSession, vault: Vault, *, contribution: int = 10, personal_min: int = 10
) -> WorldEvent:
    event = await _create_event(
        async_session,
        status=WorldEventStatus.COMPLETED,
        target_amount=10,
        personal_min=personal_min,
        reward=[{"reward_type": "caps", "amount": 250}],
    )
    event.progress_amount = 10
    async_session.add(event)
    await _create_participation(async_session, event, vault.id, contribution)
    await async_session.commit()
    return event


async def test_claim_grants_exactly_once(async_session: AsyncSession, vault: Vault) -> None:
    event = await _completed_event_with_participation(async_session, vault)
    starting_caps = vault.bottle_caps

    claim = await world_event_service.claim(async_session, vault.id)
    await async_session.refresh(vault)

    assert claim.event_id == event.id
    assert claim.claimed is True
    assert vault.bottle_caps == starting_caps + 250

    participation = await crud.world_event.get_participation(async_session, event.id, vault.id)
    assert participation is not None
    assert participation.reward_claimed_at is not None

    with pytest.raises(ResourceConflictException):
        await world_event_service.claim(async_session, vault.id)
    await async_session.refresh(vault)
    assert vault.bottle_caps == starting_caps + 250


async def test_claim_below_personal_min_raises(async_session: AsyncSession, vault: Vault) -> None:
    await _completed_event_with_participation(async_session, vault, contribution=4, personal_min=10)

    with pytest.raises(ValidationException):
        await world_event_service.claim(async_session, vault.id)


async def test_claim_while_active_raises(async_session: AsyncSession, vault: Vault) -> None:
    event = await _create_event(async_session)
    await _create_participation(async_session, event, vault.id, 10)

    with pytest.raises(ValidationException):
        await world_event_service.claim(async_session, vault.id)


async def test_claim_without_participation_raises(async_session: AsyncSession, vault: Vault) -> None:
    await _create_event(async_session, status=WorldEventStatus.COMPLETED, target_amount=10)

    with pytest.raises(ValidationException):
        await world_event_service.claim(async_session, vault.id)


# --- reads -------------------------------------------------------------------


async def test_get_state_reports_progress_without_writing(async_session: AsyncSession, vault: Vault) -> None:
    event = await _create_event(async_session)
    other_vault = await _create_vault(async_session)
    await world_event_service.record_contribution(async_session, vault.id, 6, kind=KIND)
    await world_event_service.record_contribution(async_session, other_vault.id, 4, kind=KIND)
    await async_session.commit()
    await async_session.refresh(event)

    participation = await crud.world_event.get_participation(async_session, event.id, vault.id)
    assert participation is not None
    before_event_updated_at = event.updated_at
    before_participation_updated_at = participation.updated_at
    before_participations = await _participation_count(async_session)

    state = await world_event_service.get_state(async_session, vault.id)

    assert state.event_id == event.id
    assert state.status == WorldEventStatus.ACTIVE
    assert state.kind == KIND
    assert state.progress_amount == 10
    assert state.target_amount == 100
    assert state.participant_count == 2
    assert state.contribution == 6
    assert state.personal_min == 10
    assert state.can_claim is False

    await async_session.refresh(event)
    assert await _participation_count(async_session) == before_participations
    assert event.updated_at == before_event_updated_at
    await async_session.refresh(participation)
    assert participation.updated_at == before_participation_updated_at


async def test_get_state_without_any_event_returns_empty_state(async_session: AsyncSession, vault: Vault) -> None:
    state = await world_event_service.get_state(async_session, vault.id)

    assert state.event_id is None
    assert state.status is None
    assert state.can_claim is False
    assert state.contribution == 0
