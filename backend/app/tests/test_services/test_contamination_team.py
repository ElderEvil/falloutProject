"""Tests for earned hazard teams: participation, qualification, and the bench."""

from unittest.mock import patch

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import HazardTeam, IncidentType, NotificationType
from app.models.notification import Notification
from app.models.team import ACTIVE_STATUS, RESERVE_STATUS
from app.schemas.dweller import DwellerCreate
from app.services.catalog_service import load_outfits
from app.services.combat.incident_service import incident_service
from app.services.hazard_team_service import (
    QUALIFYING_INCIDENTS,
    TEAM_SIZE,
    hazard_team_service,
)
from app.tests.test_services._hazard_team_helpers import (
    ensure_station,
    fight,
    make_member,
    outfit_data,
    raise_incident,
)
from app.utils.item_factory import build_outfit


@pytest.mark.asyncio
async def test_participation_is_recorded_once_per_incident(async_session: AsyncSession, room_with_dwellers: dict):
    """A long incident credits a defender once, however many rounds they fight."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    incident = await raise_incident(async_session, room, IncidentType.FIRE)
    dweller_ids = [dweller.id for dweller in dwellers]

    first = await crud.incident_participant_crud.record(async_session, incident.id, dweller_ids)
    second = await crud.incident_participant_crud.record(async_session, incident.id, dweller_ids)
    await async_session.commit()

    assert sorted(first) == sorted(dweller_ids)
    assert second == []
    credited = await crud.incident_participant_crud.get_credited_dweller_ids(async_session, incident.id)
    assert credited == set(dweller_ids)


@pytest.mark.asyncio
async def test_third_callout_earns_an_active_place_and_a_bio_entry(
    async_session: AsyncSession, room_with_dwellers: dict
):
    """Qualification lands on the third contamination incident, and is written into the bio."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]

    for _ in range(QUALIFYING_INCIDENTS - 1):
        await fight(async_session, room, IncidentType.FIRE, [dweller])

    assert await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dweller.id) is None

    await fight(async_session, room, IncidentType.FIRE, [dweller])

    place = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dweller.id)
    assert place is not None
    assert place.status == ACTIVE_STATUS

    await async_session.refresh(dweller)
    service_entries = [entry for entry in dweller.bio_entries if entry["source"] == "hazard"]
    assert len(service_entries) == 1
    assert "fire team" in service_entries[0]["text"]
    assert service_entries[0]["ref"]["team"] == HazardTeam.FIRE.value


@pytest.mark.asyncio
async def test_fourth_qualifier_waits_on_the_bench(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """The team holds three places; anyone who qualifies after that is benched."""
    room = room_with_dwellers["room"]
    dwellers = list(room_with_dwellers["dwellers"])
    while len(dwellers) <= TEAM_SIZE:
        dwellers.append(
            await crud.dweller.create(
                async_session,
                obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id, room_id=room.id),
            )
        )

    for _ in range(QUALIFYING_INCIDENTS):
        await fight(async_session, room, IncidentType.FIRE, dwellers)

    roster = await crud.team_crud.get_hazard_team(async_session, room.vault_id, HazardTeam.FIRE)
    assert len(roster) == TEAM_SIZE + 1
    assert sum(1 for place in roster if place.status == ACTIVE_STATUS) == TEAM_SIZE
    assert sum(1 for place in roster if place.status == RESERVE_STATUS) == 1


@pytest.mark.asyncio
async def test_fallen_member_frees_a_place_for_the_bench(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """A dead member stops holding a place, and the most senior bench member steps up."""
    room = room_with_dwellers["room"]
    dwellers = list(room_with_dwellers["dwellers"])
    while len(dwellers) <= TEAM_SIZE:
        dwellers.append(
            await crud.dweller.create(
                async_session,
                obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id, room_id=room.id),
            )
        )

    for _ in range(QUALIFYING_INCIDENTS):
        await fight(async_session, room, IncidentType.FIRE, dwellers)

    roster = await crud.team_crud.get_hazard_team(async_session, room.vault_id, HazardTeam.FIRE)
    active_place = next(place for place in roster if place.status == ACTIVE_STATUS)
    benched = next(place for place in roster if place.status == RESERVE_STATUS)

    fallen = await crud.dweller.get(async_session, active_place.dweller_id)
    fallen.is_dead = True
    async_session.add(fallen)
    await async_session.commit()

    await fight(async_session, room, IncidentType.FIRE, [dwellers[0]])

    stepped_up = await crud.team_crud.get_hazard_member(
        async_session, room.vault_id, HazardTeam.FIRE, benched.dweller_id
    )
    assert stepped_up.status == ACTIVE_STATUS
    assert await crud.team_crud.count_active_hazard(async_session, room.vault_id, HazardTeam.FIRE) == TEAM_SIZE
    roster = await crud.team_crud.get_hazard_team(async_session, room.vault_id, HazardTeam.FIRE)
    assert active_place.dweller_id not in {place.dweller_id for place in roster}


@pytest.mark.asyncio
async def test_intruder_incidents_earn_no_team_place(async_session: AsyncSession, room_with_dwellers: dict):
    """Participation is always recorded, but only contamination hazards build a team."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]

    for _ in range(QUALIFYING_INCIDENTS + 1):
        await fight(async_session, room, IncidentType.RAIDER_ATTACK, [dweller])

    for team in HazardTeam:
        assert await crud.team_crud.get_hazard_member(async_session, room.vault_id, team, dweller.id) is None
    fought = await crud.incident_participant_crud.count_incidents(
        async_session, dweller.id, frozenset({IncidentType.RAIDER_ATTACK})
    )
    assert fought == QUALIFYING_INCIDENTS + 1


@pytest.mark.asyncio
async def test_hazard_teams_are_tracked_separately(async_session: AsyncSession, room_with_dwellers: dict):
    """Fire and radiation callouts are counted apart, so a dweller can hold both places."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]

    for _ in range(QUALIFYING_INCIDENTS):
        await fight(async_session, room, IncidentType.FIRE, [dweller])
    for _ in range(QUALIFYING_INCIDENTS):
        await fight(async_session, room, IncidentType.RADSCORPION_ATTACK, [dweller])

    fire = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dweller.id)
    radiation = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.RADIATION, dweller.id)
    assert fire is not None
    assert radiation is not None


@pytest.mark.asyncio
async def test_incident_round_credits_its_defenders(async_session: AsyncSession, room_with_dwellers: dict):
    """A real combat round writes the participation that the rule reads."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    incident = await raise_incident(async_session, room, IncidentType.FIRE)

    await incident_service.process_incident(async_session, incident, 2)

    credited = await crud.incident_participant_crud.get_credited_dweller_ids(async_session, incident.id)
    assert credited == {dweller.id for dweller in dwellers}


@pytest.mark.asyncio
async def test_qualifying_round_still_commits_exactly_once(async_session: AsyncSession, room_with_dwellers: dict):
    """Earning a place during a round must not add a commit to that round."""
    room = room_with_dwellers["room"]
    dwellers = list(room_with_dwellers["dwellers"])
    for _ in range(QUALIFYING_INCIDENTS - 1):
        await fight(async_session, room, IncidentType.FIRE, dwellers)

    incident = await raise_incident(async_session, room, IncidentType.FIRE)
    await async_session.commit()

    with (
        patch.object(async_session, "commit", wraps=async_session.commit) as commit_spy,
        patch("app.services.combat.incident_math.damage_to_dwellers", return_value=0.0),
        patch("app.services.combat.incident_math.containment_progress", return_value=0.0),
    ):
        await incident_service.process_incident(async_session, incident, 2)

    assert commit_spy.await_count == 1
    place = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dwellers[0].id)
    assert place is not None
    assert place.status == ACTIVE_STATUS


@pytest.mark.asyncio
async def test_roster_reports_both_teams(async_session: AsyncSession, room_with_dwellers: dict):
    """The roster reads every team, even the ones nobody has qualified for yet."""
    room = room_with_dwellers["room"]

    roster = await hazard_team_service.get_roster(async_session, room.vault_id)

    assert {entry.team for entry in roster.teams} == set(HazardTeam)
    assert all(entry.active == [] and entry.reserve == [] for entry in roster.teams)


@pytest.mark.asyncio
async def test_roster_counts_distinct_incidents_per_hazard(async_session: AsyncSession, room_with_dwellers: dict):
    """Service count is DISTINCT incidents per hazard, not per round, and hazards don't mix."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]

    for _ in range(2):
        incident = await raise_incident(async_session, room, IncidentType.FIRE)
        await crud.incident_participant_crud.record(async_session, incident.id, [dweller.id])
        await crud.incident_participant_crud.record(async_session, incident.id, [dweller.id])
    radiation_incident = await raise_incident(async_session, room, IncidentType.RADSCORPION_ATTACK)
    await crud.incident_participant_crud.record(async_session, radiation_incident.id, [dweller.id])
    await async_session.commit()

    await make_member(async_session, room.vault_id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)
    await make_member(async_session, room.vault_id, dweller.id, HazardTeam.RADIATION, RESERVE_STATUS)

    roster = await hazard_team_service.get_roster(async_session, room.vault_id)
    fire = next(entry for entry in roster.teams if entry.team == HazardTeam.FIRE)
    radiation = next(entry for entry in roster.teams if entry.team == HazardTeam.RADIATION)

    assert fire.active[0].service_count == 2
    assert radiation.reserve[0].service_count == 1


def _outfit_catalog_entry(name: str) -> dict:
    return next(entry for entry in load_outfits() if entry["name"] == name)


async def _equip_catalog_outfit(async_session: AsyncSession, dweller_id, name: str, storage_id) -> None:
    """Equip a real catalog outfit, built through the factory so catalog-owned columns survive."""
    entry = _outfit_catalog_entry(name)
    outfit = build_outfit(entry, entry["rarity"], storage_id)
    async_session.add(outfit)
    await async_session.commit()
    await crud.outfit.equip(db_session=async_session, item_id=outfit.id, dweller_id=dweller_id)


@pytest.mark.asyncio
async def test_roster_reflects_current_equipment_not_a_cached_flag(
    async_session: AsyncSession, room_with_dwellers: dict
):
    """Gear reads the outfit worn NOW: a non-suit that still resists is not 'zero protection'."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    await make_member(async_session, room.vault_id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=room.vault_id)

    expected_resist = float(_outfit_catalog_entry("Firefighter suit, rad helmet").get("fire_resist") or 0.0)
    assert expected_resist > 0.0
    await _equip_catalog_outfit(async_session, dweller.id, "Firefighter suit, rad helmet", storage.id)

    fire = next(
        entry
        for entry in (await hazard_team_service.get_roster(async_session, room.vault_id)).teams
        if entry.team == HazardTeam.FIRE
    )
    member = fire.active[0]
    assert member.outfit_name == "Firefighter suit, rad helmet"
    assert member.has_matching_gear is False
    assert member.hazard_resist == pytest.approx(expected_resist)

    await _equip_catalog_outfit(async_session, dweller.id, "Firefighter suit", storage.id)

    fire = next(
        entry
        for entry in (await hazard_team_service.get_roster(async_session, room.vault_id)).teams
        if entry.team == HazardTeam.FIRE
    )
    member = fire.active[0]
    assert member.outfit_name == "Firefighter suit"
    assert member.has_matching_gear is True


async def _hazard_notifications(session: AsyncSession) -> list[Notification]:
    result = await session.execute(
        select(Notification).where(Notification.notification_type == NotificationType.HAZARD_TEAM_JOINED)
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_join_emits_hazard_team_joined_notification(async_session: AsyncSession, room_with_dwellers: dict):
    """Earning an active place surfaces as a bell notification with the join meta."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]

    for _ in range(QUALIFYING_INCIDENTS):
        await fight(async_session, room, IncidentType.FIRE, [dweller])

    notifications = await _hazard_notifications(async_session)
    assert len(notifications) == 1
    notification = notifications[0]
    assert notification.notification_type == NotificationType.HAZARD_TEAM_JOINED
    assert notification.title == "Hazard team"
    assert "earned a place on the vault's fire team" in notification.message
    assert notification.meta_data["dweller_id"] == str(dweller.id)
    assert notification.meta_data["dweller_name"] == dweller.display_name
    assert notification.meta_data["team"] == HazardTeam.FIRE.value
    assert notification.meta_data["status"] == ACTIVE_STATUS
    assert notification.meta_data["promoted"] is False
    assert notification.meta_data["vault_id"] == str(room.vault_id)


@pytest.mark.asyncio
async def test_qualification_loop_through_real_rounds_places_equips_and_notifies(
    async_session: AsyncSession, room_with_dwellers: dict
):
    """Three distinct FIRE incidents fought through the round engine earn the active place,
    the spares get equipped, and the bell notification fires — the playtest loop verbatim."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=room.vault_id)
    await ensure_station(async_session, room.vault_id)
    for _ in dwellers:
        await crud.outfit.create(async_session, outfit_data("Firefighter suit", storage_id=storage.id))

    for _ in range(QUALIFYING_INCIDENTS):
        incident = await raise_incident(async_session, room, IncidentType.FIRE)
        await incident_service.process_incident(async_session, incident, 2)

    for dweller in dwellers:
        place = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dweller.id)
        assert place is not None
        assert place.status == ACTIVE_STATUS
        equipped = await crud.outfit.get_equipped(async_session, dweller.id)
        assert equipped is not None
        assert equipped.name == "Firefighter suit"

    notifications = await _hazard_notifications(async_session)
    assert len(notifications) == len(dwellers)
    assert {notification.meta_data["dweller_id"] for notification in notifications} == {
        str(dweller.id) for dweller in dwellers
    }
    assert all(notification.meta_data["status"] == ACTIVE_STATUS for notification in notifications)


@pytest.mark.asyncio
async def test_bench_join_emits_bench_notification(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """A bench place surfaces with the bench message and reserve status."""
    room = room_with_dwellers["room"]
    dwellers = list(room_with_dwellers["dwellers"])
    while len(dwellers) <= TEAM_SIZE:
        dwellers.append(
            await crud.dweller.create(
                async_session,
                obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id, room_id=room.id),
            )
        )

    for _ in range(QUALIFYING_INCIDENTS):
        await fight(async_session, room, IncidentType.FIRE, dwellers)

    notifications = await _hazard_notifications(async_session)
    bench = next(notification for notification in notifications if notification.meta_data["status"] == RESERVE_STATUS)
    assert "earned a bench place on the vault's fire team" in bench.message
    assert bench.meta_data["promoted"] is False


@pytest.mark.asyncio
async def test_promotion_emits_notification_without_new_qualifier(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """A bench member stepping up is notified even when nobody newly qualifies."""
    room = room_with_dwellers["room"]
    dwellers = list(room_with_dwellers["dwellers"])
    while len(dwellers) <= TEAM_SIZE:
        dwellers.append(
            await crud.dweller.create(
                async_session,
                obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id, room_id=room.id),
            )
        )

    for _ in range(QUALIFYING_INCIDENTS):
        await fight(async_session, room, IncidentType.FIRE, dwellers)

    roster = await crud.team_crud.get_hazard_team(async_session, room.vault_id, HazardTeam.FIRE)
    active_place = next(place for place in roster if place.status == ACTIVE_STATUS)
    benched = next(place for place in roster if place.status == RESERVE_STATUS)

    fallen = await crud.dweller.get(async_session, active_place.dweller_id)
    fallen.is_dead = True
    async_session.add(fallen)
    await async_session.commit()

    # The fighting dweller already holds a place, so no new qualifier joins.
    await fight(async_session, room, IncidentType.FIRE, [dwellers[0]])

    notifications = await _hazard_notifications(async_session)
    promotion = next(
        notification
        for notification in notifications
        if notification.meta_data["dweller_id"] == str(benched.dweller_id)
        and notification.meta_data["promoted"] is True
    )
    assert promotion.meta_data["promoted"] is True
    assert promotion.meta_data["status"] == ACTIVE_STATUS
    assert "stepped up to a place on the vault's fire team" in promotion.message
