"""Tests for discovery event generation (procedural, no LLM)."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pydantic
import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.llm_interaction import LLMInteraction
from app.models.vault import Vault
from app.models.wasteland_location import LocationTypeEnum, WastelandLocation
from app.schemas.exploration_event import DiscoveryEventSchema, ExplorationEvent
from app.services.exploration.event_generator import event_generator
from app.services.exploration_service import exploration_service
from app.services.map_service import map_service


def _make_expired_exploration(exploration: Exploration) -> None:
    """Set exploration start_time far enough in the past to allow event generation."""
    exploration.start_time = datetime.utcnow() - timedelta(minutes=15)


@pytest.mark.asyncio
async def test_map_routes_preserve_repeated_discoveries_from_event_history(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """The map route comes from events, not the de-duplicated location row."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    location = await map_service.register_discovery(async_session, vault.id, exploration.id, dweller.id, "Rusty Depot")
    assert location is not None

    exploration.add_event(
        "discovery",
        "First discovery.",
        location_name=location.name,
        location_id=location.id,
        coord_x=location.coord_x,
        coord_y=location.coord_y,
    )
    exploration.add_event(
        "discovery",
        "Rediscovered on a later leg.",
        location_name=location.name,
        location_id=location.id,
        coord_x=location.coord_x,
        coord_y=location.coord_y,
    )
    async_session.add(exploration)
    await async_session.commit()

    map_payload = await map_service.get_vault_map(async_session, vault)
    assert len(map_payload.discovery_routes) == 1
    route = map_payload.discovery_routes[0]
    assert route.exploration_id == exploration.id
    assert [point.location_id for point in route.points] == [location.id, location.id]
    assert route.points[0].coord_x == round(location.coord_x * 1.6, 1)


@pytest.mark.asyncio
async def test_discovery_dict_parses_through_union():
    """A discovery dict parses through the ExplorationEvent union."""
    discovery_dict = {
        "type": "discovery",
        "description": "Your dweller has discovered Rusty Depot in the wasteland.",
        "location_name": "Rusty Depot",
    }
    adapter = pydantic.TypeAdapter(ExplorationEvent)
    parsed = adapter.validate_python(discovery_dict)
    assert isinstance(parsed, DiscoveryEventSchema)
    assert parsed.type == "discovery"
    assert parsed.location_name == "Rusty Depot"


@pytest.mark.asyncio
async def test_existing_event_weights_untouched():
    """Failure: combat/loot/danger/rest config weights are unchanged from defaults."""
    assert game_config.exploration.event_weight_combat == 35
    assert game_config.exploration.event_weight_loot == 35
    assert game_config.exploration.event_weight_danger == 20
    assert game_config.exploration.event_weight_rest == 10


@pytest.mark.asyncio
async def test_process_event_register_discovery_failure_does_not_break_event(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Failure: register_discovery raises → event still persisted, no exception propagates."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await async_session.refresh(exploration)
    _make_expired_exploration(exploration)

    mock_event = DiscoveryEventSchema(
        description="Discovery event that will fail map registration.",
        location_name="Glowing Crater",
    )

    with (
        patch.object(event_generator, "generate_event", return_value=mock_event),
        patch(
            "app.services.map_service.map_service.register_discovery",
            AsyncMock(side_effect=RuntimeError("DB connection lost")),
        ),
    ):
        result = await exploration_service.process_event(async_session, exploration)

    # Event still persisted despite map_service failure
    await async_session.refresh(result)
    assert len(result.events) == 1
    assert result.events[0]["location_name"] == "Glowing Crater"

    # No DISCOVERY WastelandLocation row (register_discovery failed)
    location_stmt = select(WastelandLocation).where(
        WastelandLocation.type == LocationTypeEnum.DISCOVERY,
        WastelandLocation.vault_id == vault.id,
    )
    locations = (await async_session.execute(location_stmt)).scalars().all()
    assert len(locations) == 0

    # No LLMInteraction rows created
    llm_count_stmt = select(LLMInteraction)
    llm_rows = (await async_session.execute(llm_count_stmt)).scalars().all()
    assert len(llm_rows) == 0
