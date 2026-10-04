"""Objective-driven incident flow: containment vs combat selection in the round engine."""

from unittest.mock import patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.incident import (
    INCIDENT_DEFINITIONS,
    IncidentDefinition,
    IncidentFamily,
    IncidentObjective,
    IncidentStatus,
    IncidentType,
)
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
    assert [event.kind for event in events] == ["containment"]


@pytest.mark.asyncio
async def test_combat_objective_uses_combat_flow(async_session: AsyncSession, room_with_dwellers: dict):
    """A DEFEAT objective fights enemies: combat formulas, kill bookkeeping, round events."""
    room = room_with_dwellers["room"]
    incident = await raise_incident(async_session, room, IncidentType.RAIDER_ATTACK)

    with (
        patch("app.services.combat.incident_math.damage_to_dwellers", return_value=10.0),
        patch("app.services.combat.incident_math.damage_to_raiders", return_value=20.0),
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

    assert result.damage_to_raiders == 20.0
    assert incident.enemies_defeated == 1  # 20.0 / (2 * 10) = one fractional kill
    assert incident.combat_progress == pytest.approx(1.0)
    assert [event.kind for event in events] == ["round"]


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
    assert [event.kind for event in events] == ["containment"]


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
    assert fire_events[0].message == "Fire containment increased by 50%."

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
    assert roach_events[0].message == "Containment increased by 50%."

    scorpion_events = await crud.incident_crud.get_recent_events(async_session, scorpion_incident.id)
    assert scorpion_events[0].message == "Radiation containment increased by 50%."


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
