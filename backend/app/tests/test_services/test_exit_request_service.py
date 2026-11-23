from datetime import timedelta
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import (
    SPECIAL_STATS,
    AgeGroupEnum,
    AvailabilityEnum,
    DwellerStatusEnum,
    GenderEnum,
    IncidentStatus,
    IncidentType,
    LifecycleEnum,
    RarityEnum,
    RoomTypeEnum,
    SPECIALEnum,
    TrainingStatus,
)
from app.core.game_config import game_config
from app.crud import training as training_crud
from app.crud.room import room as room_crud
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.combat.arena_service import arena_service
from app.services.combat.incident_service import incident_service
from app.services.exit_request_service import exit_request_service
from app.services.family.death_service import death_service
from app.services.hazard_team_service import hazard_team_service
from app.services.training_service import training_service
from app.utils.exceptions import ResourceNotFoundException, VaultOperationException
from app.utils.time import utcnow

pytestmark = pytest.mark.asyncio

EXIT = game_config.exit_request


def _dweller_data(**overrides: object) -> dict:
    data: dict = {
        "first_name": "Nora",
        "last_name": "Kell",
        "gender": GenderEnum.FEMALE,
        "rarity": RarityEnum.COMMON,
        "age_group": AgeGroupEnum.ADULT,
        "birth_date": utcnow() - timedelta(days=365 * 30),
        "level": 5,
        "experience": 0,
        "max_health": 100,
        "health": 100,
        "radiation": 0,
        "happiness": 80,
        **dict.fromkeys(SPECIAL_STATS, 3),
    }
    data.update(overrides)
    return data


async def _create(db_session: AsyncSession, vault: Vault, **overrides: object) -> Dweller:
    return await crud.dweller.create(
        db_session=db_session, obj_in=DwellerCreate(**_dweller_data(**overrides), vault_id=vault.id)
    )


async def _populate(db_session: AsyncSession, vault: Vault, count: int) -> list[Dweller]:
    """The population floor needs more than `min_population` living dwellers."""
    return [await _create(db_session, vault, first_name=f"Dw{index}") for index in range(count)]


async def _with_room_for_one_exit(db_session: AsyncSession, vault: Vault) -> list[Dweller]:
    return await _populate(db_session, vault, EXIT.min_population + 1)


async def _sad(db_session: AsyncSession, vault: Vault) -> Dweller:
    return await _create(db_session, vault, first_name="Clara", happiness=EXIT.despair_happiness)


async def _room(db_session: AsyncSession, vault: Vault, name: str, category: RoomTypeEnum, **fields) -> Room:
    payload = {
        "vault_id": vault.id,
        "name": name,
        "category": category,
        "ability": SPECIALEnum.STRENGTH,
        "base_cost": fields.pop("base_cost", 100),
        "t2_upgrade_cost": fields.pop("t2_upgrade_cost", 500),
        "t3_upgrade_cost": fields.pop("t3_upgrade_cost", 1500),
        "size_min": fields.pop("size_min", 3),
        "size_max": fields.pop("size_max", 9),
        **fields,
    }
    return await room_crud.create(db_session, RoomCreate(**payload))


async def _despair(db_session: AsyncSession, dweller: Dweller) -> Dweller:
    await crud.dweller.update(
        db_session, dweller.id, {"despair_since": utcnow() - timedelta(hours=EXIT.despair_grace_hours)}
    )
    return dweller


async def test_request_exit_records_the_ask(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)

    result = await exit_request_service.request_exit(async_session, dwellers[0].id)

    assert result.exit_requested_at is not None
    assert [d.id for d in await exit_request_service.list_pending(async_session, vault.id)] == [dwellers[0].id]


async def test_request_exit_is_refused_below_the_population_floor(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _populate(async_session, vault, EXIT.min_population)

    with pytest.raises(VaultOperationException, match="minimum population"):
        await exit_request_service.request_exit(async_session, dwellers[0].id)


async def test_request_exit_rejects_children(async_session: AsyncSession, vault: Vault) -> None:
    await _with_room_for_one_exit(async_session, vault)
    child = await _create(async_session, vault, first_name="Pip", age_group=AgeGroupEnum.CHILD)

    with pytest.raises(VaultOperationException, match="grown dwellers"):
        await exit_request_service.request_exit(async_session, child.id)


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (DwellerStatusEnum.EXPLORING, "away from the vault"),
        (DwellerStatusEnum.QUESTING, "away from the vault"),
        (DwellerStatusEnum.FIGHTING, "busy in an arena match"),
    ],
)
async def test_request_exit_rejects_a_dweller_who_is_away(
    async_session: AsyncSession, vault: Vault, status: DwellerStatusEnum, reason: str
) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)
    await crud.dweller.update(async_session, dwellers[0].id, {"status": status})

    with pytest.raises(VaultOperationException, match=reason):
        await exit_request_service.request_exit(async_session, dwellers[0].id)


async def test_request_exit_unknown_dweller(async_session: AsyncSession, vault: Vault) -> None:
    with pytest.raises(ResourceNotFoundException):
        await exit_request_service.request_exit(async_session, uuid4())


async def test_request_exit_respects_the_daily_cap(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)
    await exit_request_service.request_exit(async_session, dwellers[0].id)
    await exit_request_service.refuse_exit(async_session, vault, dwellers[0].id)

    with pytest.raises(VaultOperationException, match="last day"):
        await exit_request_service.request_exit(async_session, dwellers[1].id)


async def test_refuse_exit_resolves_the_request_and_costs_the_whole_vault(
    async_session: AsyncSession, vault: Vault
) -> None:
    """Refusing answers the ask, and every living dweller pays the morale cost."""
    dwellers = await _with_room_for_one_exit(async_session, vault)
    await exit_request_service.request_exit(async_session, dwellers[0].id)
    starts = {dweller.id: dweller.happiness for dweller in dwellers}

    refused = await exit_request_service.refuse_exit(async_session, vault, dwellers[0].id)

    penalty = EXIT.vault_refusal_happiness_penalty
    assert refused.exit_requested_at is None
    assert await exit_request_service.list_pending(async_session, vault.id) == []
    assert refused.happiness == max(10, starts[dwellers[0].id] - penalty)
    for other in dwellers[1:]:
        await async_session.refresh(other)
        assert other.happiness == max(10, starts[other.id] - penalty)


async def test_refuse_exit_without_a_request_is_rejected(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)

    with pytest.raises(VaultOperationException, match="has not asked"):
        await exit_request_service.refuse_exit(async_session, vault, dwellers[0].id)


async def test_refuse_exit_from_another_vault_is_rejected(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)
    await exit_request_service.request_exit(async_session, dwellers[0].id)

    with pytest.raises(VaultOperationException, match="does not belong"):
        await exit_request_service.refuse_exit(async_session, Vault(id=uuid4(), number=999), dwellers[0].id)


async def test_refuse_exit_happiness_is_clamped_at_ten(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)
    await exit_request_service.request_exit(async_session, dwellers[0].id)
    await crud.dweller.update(async_session, dwellers[0].id, {"happiness": 10})

    assert (await exit_request_service.refuse_exit(async_session, vault, dwellers[0].id)).happiness == 10


async def test_grant_exit_records_a_living_departure(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)
    await exit_request_service.request_exit(async_session, dwellers[0].id)

    granted = await exit_request_service.grant_exit(async_session, vault, dwellers[0].id)

    assert (granted.lifecycle, granted.availability) == (LifecycleEnum.WASTELAND, AvailabilityEnum.DEPARTURE)
    assert (granted.vault_id, granted.previous_vault_id, granted.room_id) == (None, vault.id, None)
    assert granted.departed_at is not None
    assert granted.departure_eligible_at is not None
    assert (granted.is_dead, granted.is_permanently_dead, granted.death_cause) == (False, False, None)
    assert granted.exit_requested_at is None
    assert granted.id not in [d.id for d in await exit_request_service.list_pending(async_session, vault.id)]


async def test_granted_exit_has_no_revival_window(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)
    await exit_request_service.request_exit(async_session, dwellers[0].id)

    granted = await exit_request_service.grant_exit(async_session, vault, dwellers[0].id)

    assert death_service.get_days_until_permanent(granted) is None


@pytest.mark.parametrize("member_status", ["assigned", "dispatched"])
@pytest.mark.parametrize("incident_status", [IncidentStatus.ACTIVE, IncidentStatus.SPREADING])
@pytest.mark.parametrize("success", [False, True])
async def test_grant_exit_waits_for_incident_resolution(
    async_session: AsyncSession, vault: Vault, member_status: str, incident_status: IncidentStatus, success: bool
) -> None:
    residents = await _with_room_for_one_exit(async_session, vault)
    responder = residents[0]
    await exit_request_service.request_exit(async_session, responder.id)
    requested_at, cooldown = responder.exit_requested_at, vault.last_exit_request_at
    room = await _room(async_session, vault, "Power Generator", RoomTypeEnum.PRODUCTION, size=3)
    incident = await crud.incident_crud.create(
        async_session, vault_id=vault.id, room_id=room.id, incident_type=IncidentType.FIRE, difficulty=2
    )
    await incident_service.assign_responders(async_session, incident, [responder.id])
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    members[0].status = member_status
    incident.status = incident_status
    await async_session.commit()

    with pytest.raises(VaultOperationException, match="active incident"):
        await exit_request_service.grant_exit(async_session, vault, responder.id)

    await async_session.refresh(responder)
    await async_session.refresh(vault)
    assert (responder.vault_id, responder.room_id, responder.departed_at) == (vault.id, room.id, None)
    assert responder.exit_requested_at == requested_at
    assert vault.last_exit_request_at == cooldown

    # A historical roster entry must not stop departure after either outcome.
    await crud.incident_crud.resolve(async_session, incident.id, success=success)
    granted = await exit_request_service.grant_exit(async_session, vault, responder.id)
    assert granted.vault_id is None
    assert granted.availability is AvailabilityEnum.DEPARTURE
    assert granted.exit_requested_at is None

    # A delayed return tick must close the old roster, not reclaim a departed person.
    assert await hazard_team_service.return_dispatched_responders(async_session, incident) == 0
    assert await crud.incident_crud.get_pending_responder_returns(async_session, vault.id) == []
    await async_session.refresh(responder)
    assert (responder.vault_id, responder.room_id) == (None, None)


async def test_grant_exit_cancels_active_training(async_session: AsyncSession, vault: Vault) -> None:
    """A grant stops active training inside the departure transaction, as the lifecycle contract requires."""
    dwellers = await _with_room_for_one_exit(async_session, vault)
    trainee = dwellers[0]
    room = await _room(
        async_session,
        vault,
        "Weight Room",
        RoomTypeEnum.TRAINING,
        size=2,
        capacity=6,
        base_cost=1000,
        t2_upgrade_cost=2500,
        t3_upgrade_cost=5000,
        size_min=1,
        size_max=3,
    )
    await crud.dweller.update(async_session, trainee.id, {"status": DwellerStatusEnum.IDLE, "strength": 3})
    training = await training_service.start_training(async_session, trainee.id, room.id)
    await exit_request_service.request_exit(async_session, trainee.id)

    await exit_request_service.grant_exit(async_session, vault, trainee.id)

    await async_session.refresh(training)
    assert training.status is TrainingStatus.CANCELLED
    assert training.completed_at is not None
    # The source vault's training tick only processes ACTIVE sessions, so the departed is dropped.
    assert await training_crud.training.get_active_by_vault(async_session, vault.id) == []


async def test_grant_exit_respects_the_population_floor(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)
    await exit_request_service.request_exit(async_session, dwellers[0].id)
    for dweller in dwellers[1:]:
        await crud.dweller.update(async_session, dweller.id, {"is_dead": True, "health": 0})

    with pytest.raises(VaultOperationException, match="minimum population"):
        await exit_request_service.grant_exit(async_session, vault, dwellers[0].id)


async def test_grant_exit_rejects_a_dead_dweller(async_session: AsyncSession, vault: Vault) -> None:
    """A dead dweller cannot be exiled — the pending selector must reject them."""
    dwellers = await _with_room_for_one_exit(async_session, vault)
    await exit_request_service.request_exit(async_session, dwellers[0].id)
    await crud.dweller.update(async_session, dwellers[0].id, {"is_dead": True, "health": 0})

    with pytest.raises(VaultOperationException, match="already dead"):
        await exit_request_service.grant_exit(async_session, vault, dwellers[0].id)


async def test_grant_exit_rejects_a_deleted_dweller(async_session: AsyncSession, vault: Vault) -> None:
    """A soft-deleted dweller cannot be exiled — the pending selector must reject them."""
    dwellers = await _with_room_for_one_exit(async_session, vault)
    await exit_request_service.request_exit(async_session, dwellers[0].id)
    await crud.dweller.delete(async_session, dwellers[0].id, soft=True)

    with pytest.raises(VaultOperationException, match="no longer in this vault"):
        await exit_request_service.grant_exit(async_session, vault, dwellers[0].id)


async def test_despair_makes_dwellers_ask(async_session: AsyncSession, vault: Vault) -> None:
    await _with_room_for_one_exit(async_session, vault)
    sad = await _despair(async_session, await _sad(async_session, vault))

    asked = await exit_request_service.sync_despair_requests(async_session, vault.id)

    assert [d.id for d in asked] == [sad.id]
    await async_session.refresh(sad)
    assert sad.exit_requested_at is not None


async def test_despair_needs_the_grace_period_before_asking(async_session: AsyncSession, vault: Vault) -> None:
    """A dweller must stay in despair for the grace period before the vault lets them ask."""
    await _with_room_for_one_exit(async_session, vault)
    sad = await _sad(async_session, vault)

    assert await exit_request_service.sync_despair_requests(async_session, vault.id) == []

    await _despair(async_session, sad)
    asked = await exit_request_service.sync_despair_requests(async_session, vault.id)

    assert [d.id for d in asked] == [sad.id]


async def test_the_vault_asks_at_most_once_a_day(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)
    overdue = utcnow() - timedelta(hours=EXIT.despair_grace_hours)
    for dweller in dwellers:
        await crud.dweller.update(
            async_session, dweller.id, {"happiness": EXIT.despair_happiness, "despair_since": overdue}
        )

    first = await exit_request_service.sync_despair_requests(async_session, vault.id)
    second = await exit_request_service.sync_despair_requests(async_session, vault.id)

    assert len(first) == EXIT.max_exit_requests_per_day
    assert second == []


async def test_answering_an_ask_consumes_the_day(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)
    await _despair(async_session, dwellers[0])
    await exit_request_service.request_exit(async_session, dwellers[0].id)
    vault.last_exit_request_at = None
    async_session.add(vault)
    await async_session.commit()

    await exit_request_service.refuse_exit(async_session, vault, dwellers[0].id)
    await exit_request_service.sync_despair_requests(async_session, vault.id)

    assert await exit_request_service.list_pending(async_session, vault.id) == []


async def test_despair_tracking_survives_a_blocked_ask(async_session: AsyncSession, vault: Vault) -> None:
    await _with_room_for_one_exit(async_session, vault)
    vault.last_exit_request_at = utcnow()
    async_session.add(vault)
    await async_session.commit()
    sad = await _sad(async_session, vault)

    assert await exit_request_service.sync_despair_requests(async_session, vault.id) == []

    await async_session.refresh(sad)
    assert sad.despair_since is not None


async def test_despair_raises_no_ask_below_the_population_floor(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _populate(async_session, vault, EXIT.min_population)
    for dweller in dwellers:
        await crud.dweller.update(async_session, dweller.id, {"happiness": EXIT.despair_happiness})

    assert await exit_request_service.sync_despair_requests(async_session, vault.id) == []
    for dweller in dwellers:
        await async_session.refresh(dweller)
        assert dweller.exit_requested_at is None


async def test_recovery_withdraws_a_standing_request(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)
    sad = await _sad(async_session, vault)
    await exit_request_service.request_exit(async_session, sad.id)

    await crud.dweller.update(async_session, sad.id, {"happiness": 90})
    await exit_request_service.sync_despair_requests(async_session, vault.id)

    await async_session.refresh(sad)
    assert sad.exit_requested_at is None
    assert all(d.exit_requested_at is None for d in dwellers)


async def test_recovery_withdrawal_requires_strictly_above_despair_threshold(
    async_session: AsyncSession, vault: Vault
) -> None:
    await _with_room_for_one_exit(async_session, vault)
    sad = await _sad(async_session, vault)
    await exit_request_service.request_exit(async_session, sad.id)

    await exit_request_service.sync_despair_requests(async_session, vault.id)

    await async_session.refresh(sad)
    assert sad.exit_requested_at is not None


async def test_recovery_does_not_withdraw_a_dead_dwellers_request(async_session: AsyncSession, vault: Vault) -> None:
    await _with_room_for_one_exit(async_session, vault)
    sad = await _sad(async_session, vault)
    await exit_request_service.request_exit(async_session, sad.id)
    await crud.dweller.update(async_session, sad.id, {"is_dead": True, "health": 0, "happiness": 90})

    await exit_request_service.sync_despair_requests(async_session, vault.id)

    await async_session.refresh(sad)
    assert sad.exit_requested_at is not None


async def test_despair_leaves_content_dwellers_alone(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)

    assert await exit_request_service.sync_despair_requests(async_session, vault.id) == []
    assert all(d.exit_requested_at is None for d in dwellers)


@pytest.mark.parametrize("completed", [False, True])
async def test_grant_exit_clears_idle_arena_selection(
    async_session: AsyncSession, vault: Vault, completed: bool
) -> None:
    from app.models.arena_match_event import ArenaMatchEvent

    departing, teammate, replacement, *_ = await _with_room_for_one_exit(async_session, vault)
    arena = await _room(
        async_session,
        vault,
        "Arena",
        RoomTypeEnum.ARENA,
        base_cost=800,
        t2_upgrade_cost=3000,
        t3_upgrade_cost=9000,
        size_min=6,
        size_max=6,
    )
    for dweller in (departing, teammate, replacement):
        dweller.room_id, dweller.status, dweller.health, dweller.radiation = (
            arena.id,
            DwellerStatusEnum.IDLE,
            26,
            11,
        )
    await async_session.commit()
    state = await arena_service.set_fighters(async_session, arena.id, departing.id, teammate.id)
    if completed:
        state.fight_started_at = utcnow() - timedelta(minutes=1)
        state.last_fight_at = utcnow()
    async_session.add(ArenaMatchEvent(room_id=arena.id, round_seq=1, kind="hit", message="Previous match"))
    await async_session.commit()
    await exit_request_service.request_exit(async_session, departing.id)

    await exit_request_service.grant_exit(async_session, vault, departing.id)

    await async_session.refresh(state)
    await async_session.refresh(teammate)
    assert (state.fighter_a_id, state.fighter_b_id) == (None, teammate.id)
    assert (state.fight_started_at, state.last_fight_at) == (None, None)
    assert (departing.lifecycle, departing.vault_id) == (LifecycleEnum.WASTELAND, None)
    assert (teammate.room_id, teammate.status) == (arena.id, DwellerStatusEnum.IDLE)
    assert teammate.health == departing.health == 26
    assert teammate.radiation == departing.radiation == 11
    assert (await arena_service.get_tick_snapshot(async_session, vault.id))["rooms"][0]["events"] == []
    await arena_service.set_fighters(async_session, arena.id, replacement.id, teammate.id)
    await arena_service.start_fight(async_session, arena.id)
    await async_session.refresh(teammate)
    assert teammate.status == DwellerStatusEnum.FIGHTING
