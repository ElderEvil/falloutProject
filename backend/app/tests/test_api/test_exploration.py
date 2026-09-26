"""Tests for exploration API endpoints."""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.exploration import ExplorationStatus
from app.models.room import Room
from app.models.vault import Vault
from app.models.world_location import VaultLocationState, WorldLocation
from app.schemas.common import AgeGroupEnum
from app.schemas.exploration import ExplorationCreate
from app.services.exploration_service import exploration_service
from app.services.map_service import map_service


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_send_dweller_to_wasteland_success(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    room: Room,
) -> None:
    """Test successfully sending a dweller to the wasteland."""
    dweller.room_id = room.id
    async_session.add(dweller)
    await async_session.commit()
    response = await async_client.post(
        f"/explorations/send?vault_id={vault.id}",
        json={"dweller_id": str(dweller.id), "duration": 4},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["dweller_id"] == str(dweller.id)
    assert data["vault_id"] == str(vault.id)
    assert data["status"] == ExplorationStatus.ACTIVE
    assert data["duration"] == 4

    # Verify dweller SPECIAL stats were captured
    assert data["dweller_strength"] == dweller.strength
    assert data["dweller_perception"] == dweller.perception
    assert data["dweller_endurance"] == dweller.endurance
    assert data["dweller_charisma"] == dweller.charisma
    assert data["dweller_intelligence"] == dweller.intelligence
    assert data["dweller_agility"] == dweller.agility
    assert data["dweller_luck"] == dweller.luck

    # Initial values
    assert data["total_distance"] == 0
    assert data["total_caps_found"] == 0
    assert data["enemies_encountered"] == 0
    assert data["events"] == []
    assert data["loot_collected"] == []
    await async_session.refresh(dweller)
    assert dweller.room_id is None


@pytest.mark.asyncio
async def test_list_explorations_empty(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    vault: Vault,
) -> None:
    """Test listing explorations when none exist."""
    response = await async_client.get(
        f"/explorations/vault/{vault.id}?active_only=true",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_dispatch_dweller_success(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """The dispatch endpoint accepts a clearable location and creates a targeted run."""
    await map_service.register_bio_places(async_session, dweller, origin_place="Red Rocket", visited_places=[])
    result = await async_session.execute(
        select(VaultLocationState)
        .join(WorldLocation, WorldLocation.id == VaultLocationState.location_id)
        .where(VaultLocationState.vault_id == vault.id, WorldLocation.name == "Red Rocket")
    )
    state = result.scalar_one()

    response = await async_client.post(
        f"/explorations/dispatch?vault_id={vault.id}",
        json={"dweller_id": str(dweller.id), "location_id": str(state.location_id)},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["dweller_id"] == str(dweller.id)
    assert data["vault_id"] == str(vault.id)
    assert data["status"] == ExplorationStatus.ACTIVE

    exploration = await crud.exploration.get_by_dweller(async_session, dweller_id=dweller.id)
    assert exploration is not None
    assert exploration.target_location_id == state.location_id
    assert exploration.clear_tier == 0


@pytest.mark.asyncio
async def test_get_exploration_details(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Test getting detailed exploration information."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    # Add some events and loot
    exploration = await crud.exploration.add_event(
        async_session,
        exploration_id=exploration.id,
        event_type="loot_found",
        description="Found a cool item",
        loot={"item": {"name": "Desk Fan", "rarity": "Common", "value": 10}, "caps": 15},
    )

    # The CRUD method already commits and refreshes, so data should be persisted

    response = await async_client.get(
        f"/explorations/{exploration.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(exploration.id)
    # Note: Event collection tested separately in service tests


@pytest.mark.asyncio
async def test_get_exploration_progress(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Test getting exploration progress."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    response = await async_client.get(
        f"/explorations/{exploration.id}/progress",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(exploration.id)
    assert data["status"] == ExplorationStatus.ACTIVE
    assert "progress_percentage" in data
    assert "time_remaining_seconds" in data
    assert "elapsed_time_seconds" in data
    assert "events" in data
    assert "loot_collected" in data
    assert 0 <= data["progress_percentage"] <= 100


@pytest.mark.asyncio
async def test_recall_dweller_success(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Test successfully recalling a dweller from exploration."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    # Add some loot
    exploration = await crud.exploration.add_loot(
        async_session,
        exploration_id=exploration.id,
        item_name="Desk Fan",
        quantity=1,
        rarity="Common",
    )
    exploration = await crud.exploration.update_stats(
        async_session,
        exploration_id=exploration.id,
        caps=50,
        distance=10,
        enemies=2,
    )

    # The CRUD methods already commit and refresh, so data should be persisted

    initial_caps = vault.bottle_caps

    response = await async_client.post(
        f"/explorations/{exploration.id}/recall",
        json={},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Recall only starts the return leg: no rewards and no loot until arrival.
    assert data["exploration"]["status"] == ExplorationStatus.RETURNING
    assert data["exploration"]["return_completes_at"] is not None
    assert data["rewards_summary"] is None

    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps

    # Arrival finalizes the run with reduced (recalled) rewards.
    await async_session.refresh(exploration)
    exploration.return_completes_at = datetime.utcnow() - timedelta(seconds=1)
    async_session.add(exploration)
    await async_session.commit()

    arrival = await async_client.post(
        f"/explorations/{exploration.id}/complete",
        json={},
        headers=superuser_token_headers,
    )
    assert arrival.status_code == 200
    arrival_data = arrival.json()
    assert arrival_data["exploration"]["status"] == ExplorationStatus.RECALLED
    assert arrival_data["exploration"]["end_time"] is not None

    # Check rewards summary
    rewards = arrival_data["rewards_summary"]
    assert rewards["caps"] == 50
    assert rewards["recalled_early"] is True
    assert "progress_percentage" in rewards
    # Note: loot collection tested separately

    # Verify caps transferred to vault
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 50


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_complete_exploration_success(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Test successfully completing an exploration."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    # Add some loot and stats
    exploration = await crud.exploration.add_loot(
        async_session,
        exploration_id=exploration.id,
        item_name="Desk Fan",
        quantity=1,
        rarity="Rare",
    )
    exploration = await crud.exploration.update_stats(
        async_session,
        exploration_id=exploration.id,
        caps=100,
        distance=50,
        enemies=5,
    )

    # The CRUD methods already commit and refresh, so data should be persisted

    exploration.start_time = datetime.utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.commit()

    initial_caps = vault.bottle_caps

    response = await async_client.post(
        f"/explorations/{exploration.id}/complete",
        json={},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Completion starts the return leg; the dweller must travel before rewards land.
    assert data["exploration"]["status"] == ExplorationStatus.RETURNING
    assert data["rewards_summary"] is None

    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps

    # Arrival finalizes the run and grants full rewards.
    await async_session.refresh(exploration)
    exploration.return_completes_at = datetime.utcnow() - timedelta(seconds=1)
    async_session.add(exploration)
    await async_session.commit()

    arrival = await async_client.post(
        f"/explorations/{exploration.id}/complete",
        json={},
        headers=superuser_token_headers,
    )
    assert arrival.status_code == 200
    arrival_data = arrival.json()

    assert arrival_data["exploration"]["status"] == ExplorationStatus.COMPLETED
    assert arrival_data["exploration"]["end_time"] is not None

    # Check rewards summary
    rewards = arrival_data["rewards_summary"]
    assert rewards["caps"] == 100
    assert rewards["distance"] == 50
    assert rewards["enemies_defeated"] == 5
    assert rewards["experience"] > 0  # (distance * 10) + (enemies * 50)
    # Note: loot collection tested separately
    assert not rewards.get("recalled_early")  # None for completed, True for recalled

    # Verify caps transferred to vault
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 100


@pytest.mark.asyncio
async def test_generate_event_success(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Test manually generating an event for testing."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    response = await async_client.post(
        f"/explorations/{exploration.id}/generate_event",
        json={},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Event generation is probabilistic, but exploration should be returned
    assert data["id"] == str(exploration.id)
