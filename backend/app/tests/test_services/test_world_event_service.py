from datetime import timedelta

import pytest
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.enums import NotificationType, WorldEventStatus
from app.models.notification import Notification
from app.models.vault import Vault
from app.models.world_event import WorldEvent, WorldEventParticipation
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.world_event_service import world_event_service
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ResourceConflictException, ValidationException
from app.utils.time import utcnow

KIND = "BLACKOUT_WATCH"
SOURCE = "incident"


async def _create_vault(async_session: AsyncSession) -> Vault:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    return await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))


async def seed_event(
    async_session: AsyncSession,
    *,
    status: WorldEventStatus = WorldEventStatus.ACTIVE,
    window: tuple[timedelta, timedelta] = (timedelta(hours=-1), timedelta(hours=1)),
    target: int = 100,
    progress: int = 0,
    personal_min: int = 10,
    kind: str = KIND,
    reward: list[dict] | None = None,
) -> WorldEvent:
    """Seed one event; ``window`` is the (start, end) offset from now."""
    now = utcnow()
    event = WorldEvent(
        kind=kind,
        title="Migration surge",
        description="Creatures are on the move.",
        target_amount=target,
        progress_amount=progress,
        personal_min=personal_min,
        reward=reward or [],
        starts_at=now + window[0],
        ends_at=now + window[1],
        status=status,
    )
    async_session.add(event)
    await async_session.commit()
    await async_session.refresh(event)
    return event


async def _seed_participation(
    async_session: AsyncSession, event: WorldEvent, vault_id, contribution: int
) -> WorldEventParticipation:
    participation = WorldEventParticipation(world_event_id=event.id, vault_id=vault_id, contribution=contribution)
    async_session.add(participation)
    await async_session.commit()
    await async_session.refresh(participation)
    return participation


async def _contribution(async_session: AsyncSession, event: WorldEvent, vault_id) -> int:
    participation = await crud.world_event.get_participation(async_session, event.id, vault_id)
    assert participation is not None
    return participation.contribution


async def _participation_count(async_session: AsyncSession) -> int:
    return int((await async_session.execute(select(func.count()).select_from(WorldEventParticipation))).scalar_one())


async def _credit(async_session: AsyncSession, vault_id, amount: int, *, kind: str = SOURCE) -> None:
    await world_event_service.record_contribution(async_session, vault_id, amount, kind=kind)
    await async_session.commit()


async def _completed_notifications(async_session: AsyncSession) -> list:
    result = await async_session.execute(
        select(Notification.vault_id).where(Notification.notification_type == NotificationType.WORLD_EVENT_COMPLETED)
    )
    return list(result.scalars().all())


async def test_contribution_credits_active_event(async_session: AsyncSession, vault: Vault) -> None:
    event = await seed_event(async_session)

    await _credit(async_session, vault.id, 5)
    await _credit(async_session, vault.id, 7)
    await async_session.refresh(event)

    assert await _contribution(async_session, event, vault.id) == 12
    assert event.progress_amount == 12


@pytest.mark.parametrize(
    ("seed_kwargs", "kind", "amount"),
    [
        (None, SOURCE, 7),
        ({"status": WorldEventStatus.SCHEDULED}, SOURCE, 7),
        ({}, "expedition", 7),
        ({}, SOURCE, 0),
        ({}, SOURCE, -5),
    ],
    ids=["no-event", "not-active", "foreign-source", "zero", "negative"],
)
async def test_contribution_is_noop(
    async_session: AsyncSession, vault: Vault, seed_kwargs: dict | None, kind: str, amount: int
) -> None:
    event = None if seed_kwargs is None else await seed_event(async_session, **seed_kwargs)

    await _credit(async_session, vault.id, amount, kind=kind)

    assert await _participation_count(async_session) == 0
    if event is not None:
        await async_session.refresh(event)
        assert event.progress_amount == 0


async def test_contribution_unknown_event_kind_still_credits(
    async_session: AsyncSession, vault: Vault, caplog: pytest.LogCaptureFixture
) -> None:
    event = await seed_event(async_session, kind="migration")

    await _credit(async_session, vault.id, 7)
    await async_session.refresh(event)

    assert await _participation_count(async_session) == 1
    assert event.progress_amount == 7
    assert "no contribution sources" in caplog.text


async def test_two_vaults_first_contribution_both_land(async_session: AsyncSession, vault: Vault) -> None:
    event = await seed_event(async_session)
    other_vault = await _create_vault(async_session)

    await _credit(async_session, vault.id, 4)
    await _credit(async_session, other_vault.id, 6)
    await async_session.refresh(event)

    assert await _participation_count(async_session) == 2
    assert await crud.world_event.participant_count(async_session, event.id) == 2
    assert event.progress_amount == 10


async def test_advance_activates_due_event_but_never_a_second(async_session: AsyncSession) -> None:
    window = (timedelta(minutes=-5), timedelta(hours=1))
    event = await seed_event(async_session, status=WorldEventStatus.SCHEDULED, window=window)

    assert await world_event_service.advance(async_session) == "activated"
    await async_session.refresh(event)
    assert event.status == WorldEventStatus.ACTIVE

    other = await seed_event(async_session, status=WorldEventStatus.SCHEDULED, window=window)
    assert await world_event_service.advance(async_session) is None
    await async_session.refresh(event)
    await async_session.refresh(other)

    assert event.status == WorldEventStatus.ACTIVE
    assert other.status == WorldEventStatus.SCHEDULED


async def test_advance_completion_notifies_participants_only(async_session: AsyncSession) -> None:
    event = await seed_event(async_session, target=10, progress=10)
    participants = [await _create_vault(async_session) for _ in range(2)]
    bystander = await _create_vault(async_session)
    for participant in participants:
        await _seed_participation(async_session, event, participant.id, 5)

    assert await world_event_service.advance(async_session) == "completed"
    await async_session.refresh(event)
    assert event.status == WorldEventStatus.COMPLETED

    notified = await _completed_notifications(async_session)
    assert sorted(notified) == sorted(participant.id for participant in participants)
    assert bystander.id not in notified


async def test_second_advance_does_not_renotify(async_session: AsyncSession) -> None:
    event = await seed_event(async_session, target=10, progress=10)
    vault = await _create_vault(async_session)
    await _seed_participation(async_session, event, vault.id, 10)

    await world_event_service.advance(async_session)
    await world_event_service.advance(async_session)

    assert len(await _completed_notifications(async_session)) == 1


async def test_advance_extends_once_then_expires(async_session: AsyncSession) -> None:
    now = utcnow()
    event = await seed_event(
        async_session,
        window=(timedelta(hours=-2), timedelta(minutes=-1)),
    )

    assert await world_event_service.advance(async_session) == "extended"
    await async_session.refresh(event)
    assert event.status == WorldEventStatus.ACTIVE
    assert event.extended_at is not None
    assert event.ends_at > now

    # Past the extension window: the same event can no longer be extended again.
    event.ends_at = utcnow() - timedelta(minutes=1)
    async_session.add(event)
    await async_session.commit()

    assert await world_event_service.advance(async_session) == "expired"
    await async_session.refresh(event)
    assert event.status == WorldEventStatus.EXPIRED
    assert event.extended_at is not None


async def test_claim_grants_exactly_once(async_session: AsyncSession, vault: Vault) -> None:
    event = await seed_event(
        async_session,
        status=WorldEventStatus.COMPLETED,
        target=10,
        progress=10,
        reward=[{"reward_type": "caps", "amount": 250}],
    )
    await _seed_participation(async_session, event, vault.id, 10)
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


async def test_claim_rejections(async_session: AsyncSession, vault: Vault) -> None:
    with pytest.raises(ValidationException):  # no event at all
        await world_event_service.claim(async_session, vault.id)

    event = await seed_event(async_session)
    await _seed_participation(async_session, event, vault.id, 10)
    with pytest.raises(ValidationException):  # still active
        await world_event_service.claim(async_session, vault.id)

    event.status = WorldEventStatus.COMPLETED
    event.personal_min = 20
    async_session.add(event)
    await async_session.commit()
    other_vault = await _create_vault(async_session)

    with pytest.raises(ValidationException):  # below personal min
        await world_event_service.claim(async_session, vault.id)
    with pytest.raises(ValidationException):  # never took part
        await world_event_service.claim(async_session, other_vault.id)


async def test_get_state_reports_progress_without_writing(async_session: AsyncSession, vault: Vault) -> None:
    event = await seed_event(async_session)
    other_vault = await _create_vault(async_session)
    await _credit(async_session, vault.id, 6)
    await _credit(async_session, other_vault.id, 4)
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


async def test_lifecycle_flow_activate_contribute_complete_claim(async_session: AsyncSession, vault: Vault) -> None:
    event = await seed_event(
        async_session,
        status=WorldEventStatus.SCHEDULED,
        window=(timedelta(minutes=-1), timedelta(hours=1)),
        target=5,
        personal_min=5,
        reward=[{"reward_type": "caps", "amount": 100}],
    )

    assert await world_event_service.advance(async_session) == "activated"
    await _credit(async_session, vault.id, 5)
    assert await world_event_service.advance(async_session) == "completed"

    claim = await world_event_service.claim(async_session, vault.id)
    assert claim.event_id == event.id
    assert claim.claimed is True

    with pytest.raises(ResourceConflictException):
        await world_event_service.claim(async_session, vault.id)
