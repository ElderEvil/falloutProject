"""Incident response grace: an undefended incident waits for responders.

Ticks run every 2s and spreading is disabled, so without a grace window the first
no-defender round fails the incident before the player can react.
"""

from datetime import timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import IncidentType
from app.models.vault import Vault
from app.services.combat.incident_service import incident_service
from app.services.combat.incident_sim import resolve_incident
from app.tests.test_services._hazard_team_helpers import empty_room, raise_incident
from app.utils.time import utcnow


@pytest.mark.asyncio
@pytest.mark.parametrize(("aged", "expected_status"), [(False, "active"), (True, "failed")])
async def test_undefended_incident_honors_the_grace_window(
    async_session: AsyncSession, vault: Vault, aged: bool, expected_status: str
) -> None:
    room = await empty_room(async_session, vault.id)
    incident = await raise_incident(async_session, room, IncidentType.RAIDER_ATTACK)
    if aged:
        incident.start_time = utcnow() - timedelta(hours=1)
    result = await incident_service.process_incident(async_session, incident, 2)
    assert result.no_defenders
    assert incident.status.value == expected_status


def test_sim_models_the_grace_window() -> None:
    # The offline kernel waits out an explicit grace, then fails without defenders.
    outcome = resolve_incident(IncidentType.RAIDER_ATTACK, 1, [], dt=2, duration=60, response_grace_seconds=120)
    assert outcome.failed
    assert not outcome.resolved
    assert outcome.ticks == 120 // 2 + 1
    assert outcome.damage_taken == 0
    assert outcome.deaths == 0
