import sys
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pydantic
import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import LocationTypeEnum
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.llm_interaction import LLMInteraction
from app.models.vault import Vault
from app.models.world_location import VaultLocationState
from app.schemas.exploration_event import DiscoveryEventSchema, ExplorationEvent
from app.services.exploration.event_generator import event_generator
from app.services.exploration_service import exploration_service
from app.services.map_service import map_service
from app.utils.time import utcnow

_CRATER = "Glowing Crater"


def _expire(exploration):
    # Far enough in the past to allow event generation.
    exploration.start_time = utcnow() - timedelta(minutes=15)


async def _exploration(async_session, vault, dweller):
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await async_session.refresh(exploration)
    return exploration


async def test_map_routes_preserve_repeated_discoveries_from_event_history(async_session, vault, dweller):
    exploration = await _exploration(async_session, vault, dweller)
    location = await map_service.register_discovery(async_session, vault.id, exploration.id, dweller.id, "Rusty Depot")
    assert location is not None

    for description in ("First discovery.", "Rediscovered on a later leg."):
        exploration.add_event(
            "discovery",
            description,
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


async def test_discovery_schema_and_existing_event_weights_untouched():
    discovery_dict = {
        "type": "discovery",
        "description": "Your dweller has discovered Rusty Depot in the wasteland.",
        "location_name": "Rusty Depot",
    }
    parsed = pydantic.TypeAdapter(ExplorationEvent).validate_python(discovery_dict)
    assert isinstance(parsed, DiscoveryEventSchema)
    assert parsed.type == "discovery"
    assert parsed.location_name == "Rusty Depot"

    exploration = game_config.exploration
    assert (exploration.event_weight_combat, exploration.event_weight_loot) == (35, 35)
    assert (exploration.event_weight_danger, exploration.event_weight_rest) == (20, 10)


@pytest.mark.parametrize("mode", ["raise", "import"])
async def test_process_event_survives_map_service_failure(async_session, vault, dweller, mode):
    exploration = await _exploration(async_session, vault, dweller)
    _expire(exploration)
    mock_event = DiscoveryEventSchema(
        description=f"Discovery event ({mode}) that must not break the round.", location_name=_CRATER
    )
    failure = (
        patch(
            "app.services.map_service.map_service.register_discovery",
            AsyncMock(side_effect=RuntimeError("DB connection lost")),
        )
        if mode == "raise"
        else patch.dict(sys.modules, {"app.services.map_service": None})
    )

    with patch.object(event_generator, "generate_event", return_value=mock_event), failure:
        result = await exploration_service.process_event(async_session, exploration)

    # The event is persisted and the failure never propagates.
    await async_session.refresh(result)
    assert len(result.events) == 1
    assert result.events[0]["location_name"] == _CRATER

    if mode == "raise":
        location_stmt = select(VaultLocationState).where(
            VaultLocationState.type == LocationTypeEnum.DISCOVERY, VaultLocationState.vault_id == vault.id
        )
        assert len((await async_session.execute(location_stmt)).scalars().all()) == 0
        assert len((await async_session.execute(select(LLMInteraction))).scalars().all()) == 0


async def test_discovery_records_one_bio_visit(async_session, vault, dweller):
    exploration = await _exploration(async_session, vault, dweller)
    mock_event = DiscoveryEventSchema(
        description="Your dweller has discovered Rusty Depot in the wasteland.", location_name="Rusty Depot"
    )

    with patch.object(event_generator, "generate_event", return_value=mock_event):
        for _ in range(2):
            _expire(exploration)
            await exploration_service.process_event(async_session, exploration)
            await async_session.refresh(exploration)

    refreshed = await crud.dweller.get(async_session, dweller.id)
    visits = [entry for entry in refreshed.bio_entries if entry["source"] == "exploration"]
    assert len(visits) == 1
    assert visits[0]["text"] == "Visited Rusty Depot."
    assert visits[0]["ref"]["place"] == "Rusty Depot"
