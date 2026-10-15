"""Incident response grace (game balance): an undefended incident waits for responders.

Ticks run every 2s and spreading is disabled, so without a grace window the
first no-defender round fails the incident — an empty room is a ~100% loss
before the player can react. These tests pin the grace through the real live
path (``incident_service.process_incident``) and the offline sim kernel.
"""

from datetime import datetime, timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.incident import IncidentType
from app.models.vault import Vault
from app.services.combat.incident_service import incident_service
from app.services.combat.incident_sim import resolve_incident
from app.tests.test_services._hazard_team_helpers import empty_room, raise_incident


@pytest.mark.asyncio
async def test_undefended_incident_waits_out_the_grace(async_session: AsyncSession, vault: Vault) -> None:
    """A fresh incident in an empty room stays active: the player gets time to respond."""
    room = await empty_room(async_session, vault.id)
    incident = await raise_incident(async_session, room, IncidentType.RAIDER_ATTACK)

    result = await incident_service.process_incident(async_session, incident, 2)

    assert result.no_defenders
    assert incident.status.value == "active"


@pytest.mark.asyncio
async def test_undefended_incident_fails_after_grace(async_session: AsyncSession, vault: Vault) -> None:
    """Once the grace window passes, an still-undefended incident fails as before."""
    room = await empty_room(async_session, vault.id)
    incident = await raise_incident(async_session, room, IncidentType.RAIDER_ATTACK)
    incident.start_time = datetime.utcnow() - timedelta(hours=1)

    result = await incident_service.process_incident(async_session, incident, 2)

    assert result.no_defenders
    assert incident.status.value == "failed"


def test_sim_models_the_grace_window() -> None:
    """The offline kernel waits out an explicit grace, then fails without defenders."""
    outcome = resolve_incident(IncidentType.RAIDER_ATTACK, 1, [], dt=2, duration=60, response_grace_seconds=120)
    assert outcome.failed
    assert not outcome.resolved
    assert outcome.ticks == 120 // 2 + 1
    assert outcome.damage_taken == 0
    assert outcome.deaths == 0
