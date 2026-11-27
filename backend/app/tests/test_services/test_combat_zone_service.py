"""Combat Zone service tests: lifecycle, pairing, stances, and escrow accounting."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import (
    AgeGroupEnum,
    CombatZoneMatchStatus,
    CombatZonePartyStatus,
    CombatZoneStance,
    DwellerStatusEnum,
    GenderEnum,
    IncidentStatus,
    IncidentType,
    LifecycleEnum,
    NotificationType,
    RarityEnum,
    RoomTypeEnum,
    SPECIALEnum,
)
from app.core.game_config import game_config
from app.crud.combat_zone import combat_zone_crud
from app.models.combat_zone import CombatZoneMatch
from app.models.dweller import Dweller
from app.models.incident import Incident
from app.models.notification import Notification
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreate
from app.services.combat.combat_zone_engine import CombatZoneTickStats, combat_zone_engine
from app.services.combat.combat_zone_service import combat_zone_service
from app.services.notification_service import NotificationService
from app.utils.exceptions import (
    FeatureDisabledException,
    NotFoundException,
    ResourceConflictException,
    ValidationException,
)


@pytest.fixture(autouse=True)
def combat_zone_enabled(monkeypatch):
    """Every test in this module runs with the feature on and zero travel time."""
    monkeypatch.setattr(game_config.combat_zone, "enabled", True)
    monkeypatch.setattr(game_config.combat_zone, "travel_seconds", 0)
    monkeypatch.setattr(game_config.combat_zone, "tick_seconds", 2)
    monkeypatch.setattr(game_config.combat_zone, "disconnect_grace_seconds", 10)
    monkeypatch.setattr(game_config.combat_zone, "retreat_forfeit_seconds", 6)
    monkeypatch.setattr(game_config.combat_zone, "match_max_seconds", 120)
    monkeypatch.setattr("app.services.combat.combat_zone_service.request_combat_zone_tick", lambda: None)


async def _make_user(session: AsyncSession, number: int):
    return await crud.user.create(
        db_session=session,
        obj_in=UserCreate(
            username=f"combat_zone_{number}",
            email=f"combat_zone_{number}@example.com",
            password="testpass123",
        ),
    )


async def _make_vault(session: AsyncSession, number: int, caps: int = 1_000) -> Vault:
    user = await _make_user(session, number)
    vault = await crud.vault.create_with_user_id(
        db_session=session, obj_in=VaultCreate(number=number, name=f"Combat Vault {number}"), user_id=user.id
    )
    vault.bottle_caps = caps
    session.add(vault)
    await session.commit()
    await session.refresh(vault)
    return vault


async def _make_dweller(
    session: AsyncSession,
    vault: Vault,
    *,
    first_name: str = "Fighter",
    stat: int = 5,
    level: int = 1,
    health: int = 100,
) -> Dweller:
    return await crud.dweller.create(
        db_session=session,
        obj_in=DwellerCreate(
            vault_id=vault.id,
            first_name=first_name,
            last_name="Zone",
            gender=GenderEnum.MALE,
            age_group=AgeGroupEnum.ADULT,
            rarity=RarityEnum.COMMON,
            level=level,
            max_health=health,
            health=health,
            radiation=0,
            happiness=50,
            strength=stat,
            perception=stat,
            endurance=stat,
            charisma=stat,
            intelligence=stat,
            agility=stat,
            luck=stat,
        ),
    )


async def _make_room(session: AsyncSession, vault: Vault) -> Room:
    return await crud.room.create(
        db_session=session,
        obj_in=RoomCreate(
            vault_id=vault.id,
            name="Cafeteria",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.AGILITY,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            capacity=4,
            output=10,
            size_min=1,
            size_max=3,
            size=2,
            tier=1,
            coordinate_x=0,
            coordinate_y=0,
        ),
    )


async def _deploy(session: AsyncSession, vault: Vault, dweller: Dweller):
    await combat_zone_service.send_party(session, vault.id, dweller.id)
    return await combat_zone_crud.get_party_by_vault(session, vault.id)


async def _queue(session: AsyncSession, party) -> None:
    party.status = CombatZonePartyStatus.QUEUED
    party.arrives_at = datetime.now(UTC)
    session.add(party)
    await session.commit()


async def _queued_pair(session: AsyncSession, *, stat_a: int = 5, stat_b: int = 5):
    vault_a = await _make_vault(session, 801)
    vault_b = await _make_vault(session, 802)
    dweller_a = await _make_dweller(session, vault_a, first_name="Alpha", stat=stat_a)
    dweller_b = await _make_dweller(session, vault_b, first_name="Beta", stat=stat_b)
    party_a = await _deploy(session, vault_a, dweller_a)
    party_b = await _deploy(session, vault_b, dweller_b)
    await _queue(session, party_a)
    await _queue(session, party_b)
    return vault_a, vault_b, dweller_a, dweller_b, party_a, party_b


async def _start_challenge(session: AsyncSession, vault_a: Vault, party_b) -> CombatZoneMatch:
    match_view = await combat_zone_service.challenge(session, vault_a.id, party_b.id)
    match = await combat_zone_crud.get_match(session, match_view.id)
    assert match is not None
    return match


def _tick_now(offset: int = 0) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=offset)


async def test_send_escrows_the_fee_and_detaches_the_dweller_async(async_session: AsyncSession):
    vault = await _make_vault(async_session, 812)
    room = await _make_room(async_session, vault)
    dweller = await _make_dweller(async_session, vault)
    dweller.room_id = room.id
    dweller.status = DwellerStatusEnum.WORKING
    async_session.add(dweller)
    await async_session.commit()

    party = await _deploy(async_session, vault, dweller)
    await async_session.refresh(vault)
    await async_session.refresh(dweller)

    assert party is not None
    assert party.status == CombatZonePartyStatus.TRAVELING
    assert party.escrow_caps == game_config.combat_zone.entry_fee_caps
    assert party.origin_room_id == room.id
    assert vault.bottle_caps == 1_000 - game_config.combat_zone.entry_fee_caps
    assert dweller.status == DwellerStatusEnum.FIGHTING
    assert dweller.room_id is None


async def test_send_rejects_unavailable_dwellers_and_incidents(async_session: AsyncSession):
    vault = await _make_vault(async_session, 813)
    room = await _make_room(async_session, vault)
    dweller = await _make_dweller(async_session, vault)
    dweller.status = DwellerStatusEnum.EXPLORING
    async_session.add(dweller)
    await async_session.commit()
    with pytest.raises(ValidationException, match="unavailable"):
        await combat_zone_service.send_party(async_session, vault.id, dweller.id)

    dweller.status = DwellerStatusEnum.IDLE
    dweller.is_dead = True
    async_session.add(dweller)
    await async_session.commit()
    with pytest.raises(ValidationException, match="living"):
        await combat_zone_service.send_party(async_session, vault.id, dweller.id)

    dweller.is_dead = False
    dweller.lifecycle = LifecycleEnum.DEAD_PERMANENT
    async_session.add(dweller)
    await async_session.commit()
    with pytest.raises(ValidationException, match="living"):
        await combat_zone_service.send_party(async_session, vault.id, dweller.id)

    dweller.lifecycle = LifecycleEnum.ALIVE
    async_session.add(
        Incident(
            vault_id=vault.id,
            room_id=room.id,
            type=IncidentType.RAIDER_ATTACK,
            status=IncidentStatus.ACTIVE,
            difficulty=1,
        )
    )
    await async_session.commit()
    with pytest.raises(ResourceConflictException, match="incident"):
        await combat_zone_service.send_party(async_session, vault.id, dweller.id)


async def test_send_requires_the_entry_fee_and_one_party_per_vault(async_session: AsyncSession):
    vault = await _make_vault(async_session, 814, caps=10)
    dweller = await _make_dweller(async_session, vault)
    with pytest.raises(ValidationException, match="bottle caps"):
        await combat_zone_service.send_party(async_session, vault.id, dweller.id)

    vault.bottle_caps = 1_000
    async_session.add(vault)
    await async_session.commit()
    await _deploy(async_session, vault, dweller)

    second = await _make_dweller(async_session, vault, first_name="Second")
    with pytest.raises(ResourceConflictException, match="already has a party"):
        await combat_zone_service.send_party(async_session, vault.id, second.id)


async def test_arrival_marks_the_party_queued(async_session: AsyncSession):
    vault = await _make_vault(async_session, 815)
    dweller = await _make_dweller(async_session, vault)
    party = await _deploy(async_session, vault, dweller)

    await combat_zone_service.process_ticks(async_session, now=_tick_now(1))
    await async_session.refresh(party)

    assert party.status == CombatZonePartyStatus.QUEUED
    assert party.arrives_at is not None


async def test_auto_pairing_matches_only_within_the_power_band(async_session: AsyncSession):
    # Equal power -> paired.
    vault_a = await _make_vault(async_session, 816)
    vault_b = await _make_vault(async_session, 817)
    dweller_a = await _make_dweller(async_session, vault_a, first_name="Alpha", stat=5)
    dweller_b = await _make_dweller(async_session, vault_b, first_name="Beta", stat=5)
    await _deploy(async_session, vault_a, dweller_a)
    await _deploy(async_session, vault_b, dweller_b)

    await combat_zone_service.process_ticks(async_session, now=_tick_now(1))
    matches = await combat_zone_crud.list_active_matches(async_session)
    assert len(matches) == 1
    assert matches[0].pot_caps == game_config.combat_zone.entry_fee_caps * 2

    # Wildly different power -> no auto-match.
    vault_c = await _make_vault(async_session, 818)
    vault_d = await _make_vault(async_session, 819)
    weak = await _make_dweller(async_session, vault_c, first_name="Weak", stat=1)
    strong = await _make_dweller(async_session, vault_d, first_name="Strong", stat=10, level=50)
    weak_party = await _deploy(async_session, vault_c, weak)
    await _deploy(async_session, vault_d, strong)

    await combat_zone_service.process_ticks(async_session, now=_tick_now(1))
    matches = await combat_zone_crud.list_active_matches(async_session)
    assert all(weak_party.id not in (match.party_a_id, match.party_b_id) for match in matches)


async def test_challenge_ignores_the_power_band(async_session: AsyncSession):
    vault_a, _vault_b, _dweller_a, _dweller_b, _party_a, party_b = await _queued_pair(
        async_session, stat_a=1, stat_b=10
    )
    match = await _start_challenge(async_session, vault_a, party_b)
    assert match.status == CombatZoneMatchStatus.ACTIVE
    assert match.pot_caps == game_config.combat_zone.entry_fee_caps * 2


async def test_rounds_alternate_and_journal_each_hit(async_session: AsyncSession):
    vault_a, _vault_b, dweller_a, dweller_b, _party_a, party_b = await _queued_pair(async_session)
    match = await _start_challenge(async_session, vault_a, party_b)

    await combat_zone_service.process_ticks(async_session, now=_tick_now(0), seconds_passed=2)
    await async_session.refresh(match)
    await async_session.refresh(dweller_b)
    assert match.next_attack_party == "B"
    assert match.round_seq == 2
    assert dweller_b.health < 100

    events = await combat_zone_crud.list_events(async_session, match.id)
    assert [event.kind for event in events] == ["system", "hit"]
    assert "Alpha" in events[1].message


async def test_silence_defaults_to_defensive_without_forfeiting(async_session: AsyncSession):
    vault_a, _vault_b, _dweller_a, dweller_b, party_a, party_b = await _queued_pair(async_session)
    match = await _start_challenge(async_session, vault_a, party_b)
    party_a.stance = CombatZoneStance.AGGRESSIVE
    party_a.stance_updated_at = datetime.now(UTC) - timedelta(seconds=30)
    async_session.add(party_a)
    await async_session.commit()

    await combat_zone_service.process_ticks(async_session, now=_tick_now(0), seconds_passed=2)
    await async_session.refresh(party_a)
    await async_session.refresh(match)

    assert party_a.stance == CombatZoneStance.DEFENSIVE
    assert match.status == CombatZoneMatchStatus.ACTIVE
    assert dweller_b.health < 100


async def test_retreat_forfeits_the_pot_to_the_opponent(async_session: AsyncSession):
    vault_a, vault_b, _dweller_a, _dweller_b, party_a, party_b = await _queued_pair(async_session)
    match = await _start_challenge(async_session, vault_a, party_b)
    party_a.stance = CombatZoneStance.RETREAT
    party_a.stance_updated_at = datetime.now(UTC) - timedelta(seconds=30)
    async_session.add(party_a)
    await async_session.commit()

    await combat_zone_service.process_ticks(async_session, now=_tick_now(0), seconds_passed=2)
    await async_session.refresh(match)
    await async_session.refresh(vault_b)

    assert match.status == CombatZoneMatchStatus.FINISHED
    assert match.finish_reason == "retreat"
    assert match.winner_party_id == party_b.id
    assert vault_b.bottle_caps == 1_000 - game_config.combat_zone.entry_fee_caps + match.pot_caps


async def test_victory_is_non_lethal_and_pays_the_winner(async_session: AsyncSession):
    vault_a, vault_b, _dweller_a, dweller_b, party_a, party_b = await _queued_pair(async_session)
    match = await _start_challenge(async_session, vault_a, party_b)
    dweller_b.health = 1
    async_session.add(dweller_b)
    await async_session.commit()

    await combat_zone_service.process_ticks(async_session, now=_tick_now(0), seconds_passed=2)
    await async_session.refresh(match)
    await async_session.refresh(dweller_b)
    await async_session.refresh(vault_a)

    assert match.status == CombatZoneMatchStatus.FINISHED
    assert match.finish_reason == "victory"
    assert match.winner_party_id == party_a.id
    assert dweller_b.health == 25
    assert vault_a.bottle_caps == 1_000 - game_config.combat_zone.entry_fee_caps + match.pot_caps


async def test_timeout_with_equal_hp_refunds_both_fees(async_session: AsyncSession):
    vault_a, vault_b, _dweller_a, _dweller_b, _party_a, party_b = await _queued_pair(async_session)
    match = await _start_challenge(async_session, vault_a, party_b)
    match.max_ends_at = datetime.now(UTC) - timedelta(seconds=1)
    async_session.add(match)
    await async_session.commit()

    await combat_zone_service.process_ticks(async_session, now=_tick_now(0), seconds_passed=2)
    await async_session.refresh(match)
    await async_session.refresh(vault_a)
    await async_session.refresh(vault_b)

    assert match.status == CombatZoneMatchStatus.FINISHED
    assert match.finish_reason == "timeout"
    assert match.winner_party_id is None
    assert vault_a.bottle_caps == 1_000
    assert vault_b.bottle_caps == 1_000


async def test_recall_while_queued_refunds_and_returns(async_session: AsyncSession):
    vault = await _make_vault(async_session, 820)
    dweller = await _make_dweller(async_session, vault)
    party = await _deploy(async_session, vault, dweller)
    await _queue(async_session, party)

    returned = await combat_zone_service.recall_party(async_session, vault.id)
    await async_session.refresh(vault)

    assert returned.status == CombatZonePartyStatus.RETURNING
    assert returned.escrow_caps == 0
    assert vault.bottle_caps == 1_000


async def test_return_restores_the_origin_room(async_session: AsyncSession):
    vault = await _make_vault(async_session, 821)
    room = await _make_room(async_session, vault)
    dweller = await _make_dweller(async_session, vault)
    dweller.room_id = room.id
    dweller.status = DwellerStatusEnum.WORKING
    async_session.add(dweller)
    await async_session.commit()

    party = await _deploy(async_session, vault, dweller)
    party.arrives_at = datetime.now(UTC) - timedelta(seconds=1)
    party.status = CombatZonePartyStatus.RETURNING
    async_session.add(party)
    await async_session.commit()

    await combat_zone_service.process_ticks(async_session, now=_tick_now(1))
    await async_session.refresh(party)
    await async_session.refresh(dweller)

    assert party.status == CombatZonePartyStatus.HOME
    assert dweller.room_id == room.id
    assert dweller.status == DwellerStatusEnum.WORKING


async def test_finished_match_settles_exactly_once(async_session: AsyncSession):
    vault_a, _vault_b, _dweller_a, dweller_b, party_a, party_b = await _queued_pair(async_session)
    match = await _start_challenge(async_session, vault_a, party_b)
    dweller_b.health = 1
    async_session.add(dweller_b)
    await async_session.commit()

    await combat_zone_service.process_ticks(async_session, now=_tick_now(0), seconds_passed=2)
    await async_session.refresh(match)
    await async_session.refresh(vault_a)
    balance = vault_a.bottle_caps

    await combat_zone_engine._finish_match(async_session, match, party_a, "victory", _tick_now(1))
    await async_session.commit()
    await async_session.refresh(vault_a)

    assert vault_a.bottle_caps == balance


async def test_tick_returns_typed_stats(async_session: AsyncSession):
    stats = await combat_zone_service.process_ticks(async_session, now=_tick_now(0))

    assert isinstance(stats, CombatZoneTickStats)
    assert (stats.matches, stats.paired, stats.arrived, stats.returned) == (0, 0, 0, 0)
    assert stats.skipped is None


async def test_finished_match_history_survives_party_reuse(async_session: AsyncSession):
    vault_a, _vault_b, dweller_a, dweller_b, _party_a, party_b = await _queued_pair(async_session)
    match = await _start_challenge(async_session, vault_a, party_b)
    dweller_b.health = 1
    async_session.add(dweller_b)
    await async_session.commit()

    await combat_zone_service.process_ticks(async_session, now=_tick_now(0), seconds_passed=2)
    await combat_zone_service.process_ticks(async_session, now=_tick_now(1))

    replacement = await _make_dweller(async_session, vault_a, first_name="Replacement")
    await combat_zone_service.send_party(async_session, vault_a.id, replacement.id)

    view = await combat_zone_service.get_match(async_session, match.id, viewer_user_id=vault_a.user_id)
    assert view.party_a.fighter.id == str(dweller_a.id)
    assert view.party_a.fighter.name == dweller_a.display_name
    assert view.party_a.vault_number == vault_a.number


async def test_disabling_the_zone_finishes_live_matches_and_refunds(async_session: AsyncSession, monkeypatch):
    vault_a, vault_b, _dweller_a, _dweller_b, _party_a, party_b = await _queued_pair(async_session)
    match = await _start_challenge(async_session, vault_a, party_b)
    monkeypatch.setattr(game_config.combat_zone, "enabled", False)

    stats = await combat_zone_service.process_ticks(async_session, now=_tick_now(0))
    await async_session.refresh(match)
    await async_session.refresh(vault_a)
    await async_session.refresh(vault_b)

    assert match.status == CombatZoneMatchStatus.FINISHED
    assert match.finish_reason == "draw"
    assert vault_a.bottle_caps == 1_000
    assert vault_b.bottle_caps == 1_000
    assert stats.pending == 2

    await combat_zone_service.process_ticks(async_session, now=_tick_now(1))
    for vault in (vault_a, vault_b):
        party = await combat_zone_crud.get_party_by_vault(async_session, vault.id)
        assert party is not None
        assert party.status == CombatZonePartyStatus.HOME
        assert party.escrow_caps == 0


async def test_match_cursor_and_incremental_events(async_session: AsyncSession):
    vault_a, _vault_b, _dweller_a, dweller_b, _party_a, party_b = await _queued_pair(async_session)
    match = await _start_challenge(async_session, vault_a, party_b)
    await combat_zone_service.process_ticks(async_session, now=_tick_now(0), seconds_passed=2)

    view = await combat_zone_service.get_match(async_session, match.id, viewer_user_id=vault_a.user_id)
    assert view.cursor.sequence == view.events[-1].sequence
    assert view.cursor.status == "active"
    first_sequence = view.events[0].sequence
    incremental = await combat_zone_service.get_events(
        async_session, view.id, after_sequence=first_sequence, viewer_user_id=vault_a.user_id
    )
    assert incremental
    assert all(event.sequence > first_sequence for event in incremental)

    dweller_b.health = 1
    async_session.add(dweller_b)
    await async_session.commit()
    await combat_zone_service.process_ticks(async_session, now=_tick_now(1), seconds_passed=2)
    await combat_zone_service.process_ticks(async_session, now=_tick_now(2), seconds_passed=2)

    finished = await combat_zone_service.get_match(async_session, view.id, viewer_user_id=vault_a.user_id)
    assert finished.cursor.status == "finished"
    assert finished.cursor.sequence == finished.events[-1].sequence


async def test_winner_credit_reports_the_capped_amount(async_session: AsyncSession):
    vault_a, _vault_b, _dweller_a, dweller_b, _party_a, party_b = await _queued_pair(async_session)
    vault_a.bottle_caps = 999_990
    async_session.add(vault_a)
    await async_session.commit()
    match = await _start_challenge(async_session, vault_a, party_b)
    dweller_b.health = 1
    async_session.add(dweller_b)
    await async_session.commit()

    await combat_zone_service.process_ticks(async_session, now=_tick_now(0), seconds_passed=2)

    view = await combat_zone_service.get_match(async_session, match.id, viewer_user_id=vault_a.user_id)
    assert view.party_a.is_winner is True
    assert view.party_a.credited_caps == 9
    rows = (
        (
            await async_session.execute(
                select(Notification).where(
                    Notification.user_id == vault_a.user_id,
                    Notification.notification_type == NotificationType.COMBAT_VICTORY,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert "9 caps" in rows[0].message
