"""Tests for exploration API endpoints."""

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.exploration import ExplorationStatus
from app.models.vault import Vault
from app.schemas.exploration import ExplorationCreate


@pytest.mark.asyncio
async def test_send_dweller_to_wasteland_success(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Test successfully sending a dweller to the wasteland."""
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


@pytest.mark.asyncio
async def test_send_dweller_already_exploring(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Test error when dweller is already on an exploration."""
    # Create an active exploration for the dweller
    exploration_in = ExplorationCreate(  # noqa: F841
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Try to send the same dweller again
    response = await async_client.post(
        f"/explorations/send?vault_id={vault.id}",
        json={"dweller_id": str(dweller.id), "duration": 4},
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert "already on an exploration" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_explorations_active_only(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Test listing only active explorations for a vault."""
    # Create active exploration
    active_exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Create completed exploration
    from app.schemas.dweller import DwellerCreate  # noqa: PLC0415
    from app.tests.factory.dwellers import create_fake_dweller  # noqa: PLC0415

    dweller2_data = create_fake_dweller()
    dweller2_data["vault_id"] = vault.id
    dweller2 = await crud.dweller.create(async_session, DwellerCreate(**dweller2_data))

    completed_exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller2.id,
        duration=4,
    )
    await crud.exploration.complete_exploration(async_session, exploration_id=completed_exploration.id)

    # List active only
    response = await async_client.get(
        f"/explorations/vault/{vault.id}?active_only=true",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(active_exploration.id)
    assert data[0]["status"] == ExplorationStatus.ACTIVE


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
async def test_get_exploration_details(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Test getting detailed exploration information."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

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
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

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
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

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

    assert data["exploration"]["status"] == ExplorationStatus.RECALLED
    assert data["exploration"]["end_time"] is not None

    # Check rewards summary
    rewards = data["rewards_summary"]
    assert rewards["caps"] == 50
    assert rewards["recalled_early"] is True
    assert "progress_percentage" in rewards
    # Note: loot collection tested separately

    # Verify caps transferred to vault
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 50


@pytest.mark.asyncio
async def test_recall_dweller_not_active(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Test error when trying to recall a completed exploration."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    await crud.exploration.complete_exploration(async_session, exploration_id=exploration.id)

    response = await async_client.post(
        f"/explorations/{exploration.id}/recall",
        json={},
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert "not active" in response.json()["detail"]


@pytest.mark.asyncio
async def test_complete_exploration_success(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Test successfully completing an exploration."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

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

    initial_caps = vault.bottle_caps

    response = await async_client.post(
        f"/explorations/{exploration.id}/complete",
        json={},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["exploration"]["status"] == ExplorationStatus.COMPLETED
    assert data["exploration"]["end_time"] is not None

    # Check rewards summary
    rewards = data["rewards_summary"]
    assert rewards["caps"] == 100
    assert rewards["distance"] == 50
    assert rewards["enemies_defeated"] == 5
    assert rewards["experience"] > 0  # (distance * 10) + (enemies * 50)
    # Note: loot collection tested separately
    assert "recalled_early" not in rewards or rewards["recalled_early"] is False

    # Verify caps transferred to vault
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 100


@pytest.mark.asyncio
async def test_complete_exploration_not_active(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Test error when trying to complete a recalled exploration."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    await crud.exploration.recall_exploration(async_session, exploration_id=exploration.id)

    response = await async_client.post(
        f"/explorations/{exploration.id}/complete",
        json={},
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert "not active" in response.json()["detail"]


@pytest.mark.asyncio
async def test_generate_event_success(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Test manually generating an event for testing."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    response = await async_client.post(
        f"/explorations/{exploration.id}/generate_event",
        json={},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Event generation is probabilistic, but exploration should be returned
    assert data["id"] == str(exploration.id)


@pytest.mark.asyncio
async def test_generate_event_not_active(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Test error when trying to generate event for inactive exploration."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    await crud.exploration.complete_exploration(async_session, exploration_id=exploration.id)

    response = await async_client.post(
        f"/explorations/{exploration.id}/generate_event",
        json={},
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert "not active" in response.json()["detail"]
