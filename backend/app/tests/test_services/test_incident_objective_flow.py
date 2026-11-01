"""Objective-driven incident flow: containment vs combat selection in the round engine."""

from unittest.mock import patch
from uuid import UUID

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import IncidentFamily, IncidentObjective, IncidentStatus, IncidentType
from app.models.incident import INCIDENT_DEFINITIONS, IncidentDefinition
from app.services.combat.incident_service import incident_service
from app.tests.test_services._hazard_team_helpers import raise_incident


def _containment_definition() -> IncidentDefinition:
    return IncidentDefinition(
        family=IncidentFamily.HAZARD,
        objective=IncidentObjective.CONTAIN,
        progress_label="Infestation contained",
        response_label="Send responders",
        risk_kind="spread",
    )


async def test_combat_hits_identify_each_actor_and_target_for_playback(async_session, room_with_dwellers):
    room = room_with_dwellers["room"]
    incident = await raise_incident(async_session, room, IncidentType.RAIDER_ATTACK)

    await incident_service.process_incident(async_session, incident, 2)
    view = await incident_service.get_incident_read(async_session, incident, room.name)
    attacks = [event for event in view.events if event.kind == "hit"]

    assert attacks
    assert all(event.action is not None and event.action.skill is None for event in attacks)
    outgoing = [event.action for event in attacks if event.action.actor_id != "threat"]
    incoming = [event.action for event in attacks if event.action.actor_id == "threat"]
    assert outgoing
    assert incoming
    assert all(action.targets[0].target_id == "threat" for action in outgoing)
    for action in incoming:
        impact = action.targets[0]
        dweller = await crud.dweller.get(async_session, UUID(impact.target_id))
        assert impact.health_after == dweller.health
        assert impact.health_before > impact.health_after


async def test_incident_late_failure_rolls_back_actions_and_health(async_session, room_with_dwellers, monkeypatch):
    from sqlalchemy import event
    from sqlalchemy.exc import SQLAlchemyError

    from app.services.combat import incident_publishing

    room = room_with_dwellers["room"]
    incident = await raise_incident(async_session, room, IncidentType.RAIDER_ATTACK)
    incident_id = incident.id
    dweller = room_with_dwellers["dwellers"][0]
    dweller_id, health_before = dweller.id, dweller.health
    delivered = []

    async def delivery(*args, **kwargs):
        delivered.append(True)

    monkeypatch.setattr(incident_publishing, "publish_sse", delivery)
    monkeypatch.setattr(incident_publishing, "notify_resolution", delivery)
    connection = (await async_session.connection()).sync_connection
    writes = set()

    def fail_after_writes(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO incident_event"):
            writes.add("action")
        if statement.startswith("UPDATE dweller") and "health" in statement:
            writes.add("health")
        if writes == {"action", "health"}:
            raise SQLAlchemyError("late incident failure")

    event.listen(connection, "after_cursor_execute", fail_after_writes)
    try:
        with pytest.raises(SQLAlchemyError, match="late incident failure"):
            await incident_service.process_incident(async_session, incident, 2)
    finally:
        event.remove(connection, "after_cursor_execute", fail_after_writes)
    await async_session.rollback()
    reloaded = await crud.dweller.get(async_session, dweller_id)
    restored = await crud.incident_crud.get(async_session, incident_id)
    assert reloaded.health == health_before
    assert restored.combat_progress == 0
    assert not await crud.incident_crud.get_recent_events(async_session, incident_id)
    assert not delivered


@pytest.mark.asyncio
async def test_containment_objective_uses_containment_flow(async_session: AsyncSession, room_with_dwellers: dict):
    """A CONTAIN objective suppresses the hazard: containment formulas, no kill bookkeeping."""
    room = room_with_dwellers["room"]
    incident = await raise_incident(async_session, room, IncidentType.FIRE)

    with (
        patch("app.services.combat.incident_math.containment_damage", return_value=10.0),
        patch("app.services.combat.incident_math.containment_progress", return_value=0.5),
        patch("app.services.combat.incident_math.damage_to_dwellers", side_effect=AssertionError("combat damage used")),
        patch(
            "app.services.combat.incident_math.damage_to_raiders", side_effect=AssertionError("combat progress used")
        ),
    ):
        result = await incident_service.process_incident(async_session, incident, 2)

    await async_session.refresh(incident)
    events = await crud.incident_crud.get_recent_events(async_session, incident.id)

    assert result.damage_to_dwellers == 10.0
    assert result.damage_to_raiders == 0.0
    assert result.enemies_defeated == 0
    assert incident.enemies_defeated == 0
    assert incident.combat_progress == pytest.approx(0.5)
    assert events[-1].kind == "turn"
    assert next(event for event in events if event.kind == "containment").data == {
        "target": "hazard",
        "amount": 0.5,
    }
    hit_kinds = [event.kind for event in events if event.kind not in ("turn", "containment")]
    assert hit_kinds
    assert all(kind == "hit" for kind in hit_kinds)


@pytest.mark.asyncio
async def test_combat_objective_uses_combat_flow(async_session: AsyncSession, room_with_dwellers: dict):
    """A DEFEAT objective fights enemies: combat formulas, kill bookkeeping, round events."""
    room = room_with_dwellers["room"]
    incident = await raise_incident(async_session, room, IncidentType.RAIDER_ATTACK)

    with (
        patch("app.services.combat.incident_math.damage_to_dwellers", return_value=10.0),
        patch("app.services.combat.incident_math.damage_to_raiders", return_value=40.0),
        patch(
            "app.services.combat.incident_math.containment_damage",
            side_effect=AssertionError("containment damage used"),
        ),
        patch(
            "app.services.combat.incident_math.containment_progress",
            side_effect=AssertionError("containment progress used"),
        ),
    ):
        result = await incident_service.process_incident(async_session, incident, 2)

    await async_session.refresh(incident)
    events = await crud.incident_crud.get_recent_events(async_session, incident.id)

    assert result.damage_to_raiders == 40.0
    assert incident.enemies_defeated == 1  # 40.0 / (2 * 10 * 2.0) = one kill
    assert incident.combat_progress == pytest.approx(1.0)
    assert events[-1].kind == "turn"
    assert events[-1].message == "Responders attack"
    threat_hits = [event for event in events if event.data and "damage_to_threat" in event.data]
    dweller_hits = [event for event in events if event.data and "damage_to_dwellers" in event.data]
    assert all(event.kind == "hit" for event in threat_hits + dweller_hits)
    assert sum(event.data["damage_to_threat"] for event in threat_hits) == 40
    assert sum(event.data["damage_to_dwellers"] for event in dweller_hits) == incident.damage_dealt
    assert any("hits the raiders" in event.message for event in threat_hits)


@pytest.mark.asyncio
async def test_non_fire_containment_definition_uses_containment_flow(
    async_session: AsyncSession, room_with_dwellers: dict, monkeypatch: pytest.MonkeyPatch
):
    """A non-fire hazard declaring CONTAIN follows the containment path, not combat."""
    monkeypatch.setitem(INCIDENT_DEFINITIONS, IncidentType.RADROACH_INFESTATION, _containment_definition())
    room = room_with_dwellers["room"]
    incident = await raise_incident(async_session, room, IncidentType.RADROACH_INFESTATION)

    with (
        patch("app.services.combat.incident_math.containment_damage", return_value=10.0),
        patch("app.services.combat.incident_math.containment_progress", return_value=0.5),
        patch("app.services.combat.incident_math.damage_to_dwellers", side_effect=AssertionError("combat damage used")),
        patch(
            "app.services.combat.incident_math.damage_to_raiders", side_effect=AssertionError("combat progress used")
        ),
    ):
        result = await incident_service.process_incident(async_session, incident, 2)

    await async_session.refresh(incident)
    events = await crud.incident_crud.get_recent_events(async_session, incident.id)

    assert result.damage_to_raiders == 0.0
    assert result.enemies_defeated == 0
    assert incident.enemies_defeated == 0
    assert incident.combat_progress == pytest.approx(0.5)
    assert events[-1].kind == "turn"
    assert next(event for event in events if event.kind == "containment").data == {
        "target": "hazard",
        "amount": 0.5,
    }


@pytest.mark.asyncio
async def test_non_fire_containment_resolves_on_full_progress(
    async_session: AsyncSession, room_with_dwellers: dict, monkeypatch: pytest.MonkeyPatch
):
    """Containment resolution keys off combat_progress, whatever the incident type."""
    monkeypatch.setitem(INCIDENT_DEFINITIONS, IncidentType.RADROACH_INFESTATION, _containment_definition())
    room = room_with_dwellers["room"]
    incident = await raise_incident(async_session, room, IncidentType.RADROACH_INFESTATION)
    incident.combat_progress = 0.99
    async_session.add(incident)
    await async_session.commit()

    with (
        patch("app.services.combat.incident_math.containment_damage", return_value=0.0),
        patch("app.services.combat.incident_math.containment_progress", return_value=0.02),
    ):
        await incident_service.process_incident(async_session, incident, 2)

    await async_session.refresh(incident)
    assert incident.status == IncidentStatus.RESOLVED


@pytest.mark.asyncio
async def test_combat_objective_does_not_resolve_on_progress_alone(
    async_session: AsyncSession, room_with_dwellers: dict
):
    """Combat resolution keys off kills, so full combat_progress alone is not a victory."""
    room = room_with_dwellers["room"]
    incident = await raise_incident(async_session, room, IncidentType.RAIDER_ATTACK)
    incident.combat_progress = 1.0
    async_session.add(incident)
    await async_session.commit()

    with (
        patch("app.services.combat.incident_math.damage_to_dwellers", return_value=0.0),
        patch("app.services.combat.incident_math.damage_to_raiders", return_value=0.0),
    ):
        await incident_service.process_incident(async_session, incident, 2)

    await async_session.refresh(incident)
    assert incident.status == IncidentStatus.ACTIVE


@pytest.mark.asyncio
async def test_containment_message_is_specific_per_hazard(
    async_session: AsyncSession, room_with_dwellers: dict, monkeypatch: pytest.MonkeyPatch
):
    """Containment copy follows the hazard: fire, radiation, or neutral for the rest."""
    room = room_with_dwellers["room"]
    fire_incident = await raise_incident(async_session, room, IncidentType.FIRE)

    with (
        patch("app.services.combat.incident_math.containment_damage", return_value=10.0),
        patch("app.services.combat.incident_math.containment_progress", return_value=0.5),
    ):
        await incident_service.process_incident(async_session, fire_incident, 2)

    fire_events = await crud.incident_crud.get_recent_events(async_session, fire_incident.id)
    assert next(event.message for event in fire_events if event.kind == "containment") == (
        "Fire containment increased by 50%."
    )

    monkeypatch.setitem(INCIDENT_DEFINITIONS, IncidentType.RADROACH_INFESTATION, _containment_definition())
    monkeypatch.setitem(INCIDENT_DEFINITIONS, IncidentType.RADSCORPION_ATTACK, _containment_definition())
    roach_incident = await raise_incident(async_session, room, IncidentType.RADROACH_INFESTATION)
    scorpion_incident = await raise_incident(async_session, room, IncidentType.RADSCORPION_ATTACK)

    with (
        patch("app.services.combat.incident_math.containment_damage", return_value=10.0),
        patch("app.services.combat.incident_math.containment_progress", return_value=0.5),
    ):
        await incident_service.process_incident(async_session, roach_incident, 2)
        await incident_service.process_incident(async_session, scorpion_incident, 2)

    roach_events = await crud.incident_crud.get_recent_events(async_session, roach_incident.id)
    assert next(event.message for event in roach_events if event.kind == "containment") == (
        "Containment increased by 50%."
    )

    scorpion_events = await crud.incident_crud.get_recent_events(async_session, scorpion_incident.id)
    assert next(event.message for event in scorpion_events if event.kind == "containment") == (
        "Radiation containment increased by 50%."
    )


@pytest.mark.asyncio
async def test_non_fire_containment_read_reports_percentage_progress(
    async_session: AsyncSession, room_with_dwellers: dict, monkeypatch: pytest.MonkeyPatch
):
    """The read contract reports containment as a percentage for any CONTAIN objective."""
    monkeypatch.setitem(INCIDENT_DEFINITIONS, IncidentType.RADROACH_INFESTATION, _containment_definition())
    room = room_with_dwellers["room"]
    incident = await raise_incident(async_session, room, IncidentType.RADROACH_INFESTATION)
    incident.combat_progress = 0.5
    async_session.add(incident)
    await async_session.commit()

    read = await incident_service.get_incident_read(async_session, incident, room.name)

    assert read.objective == IncidentObjective.CONTAIN
    assert read.progress.current == 50
    assert read.progress.target == 100
