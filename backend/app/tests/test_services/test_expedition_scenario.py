"""Tests for the expedition-scenario dev/QA provisioning service."""

from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.exploration import ExplorationStatus
from app.models.vault import Vault
from app.services.exploration.expedition_scenario_service import expedition_scenario_service
from app.utils.exceptions import ResourceNotFoundException


@pytest.mark.asyncio
async def test_setup_creates_level_five_dweller_on_active_exploration(
    async_session: AsyncSession, vault: Vault
) -> None:
    result = await expedition_scenario_service.setup(
        async_session, vault_id=vault.id, dweller_level=5, duration_hours=8
    )

    assert result.created_vault is False
    assert result.vault.id == vault.id
    assert result.dweller.level == 5
    assert result.dweller.display_name == "Scout Scenario"
    assert result.exploration.status == ExplorationStatus.ACTIVE
    assert result.exploration.duration == 8
    assert {site.id for site in result.available_sites} == {"red_rocket", "super_duper_mart"}
    assert result.precleared_site_id is None


@pytest.mark.asyncio
async def test_setup_level_four_gates_super_duper_mart(async_session: AsyncSession, vault: Vault) -> None:
    result = await expedition_scenario_service.setup(
        async_session, vault_id=vault.id, dweller_level=4, duration_hours=8
    )

    assert result.dweller.level == 4
    assert [site.id for site in result.available_sites] == ["red_rocket"]


@pytest.mark.asyncio
async def test_setup_preclear_hides_site_from_picker(async_session: AsyncSession, vault: Vault) -> None:
    result = await expedition_scenario_service.setup(
        async_session, vault_id=vault.id, dweller_level=5, duration_hours=8, preclear_site_id="red_rocket"
    )

    assert result.precleared_site_id == "red_rocket"
    assert "red_rocket" not in {site.id for site in result.available_sites}
    assert "super_duper_mart" in {site.id for site in result.available_sites}


@pytest.mark.asyncio
async def test_setup_unknown_preclear_site_raises(async_session: AsyncSession, vault: Vault) -> None:
    with pytest.raises(ValueError, match="Unknown expedition site"):
        await expedition_scenario_service.setup(
            async_session, vault_id=vault.id, dweller_level=5, duration_hours=8, preclear_site_id="nope"
        )
    assert await crud.exploration.get_by_vault(async_session, vault_id=vault.id, active_only=True) == []


@pytest.mark.asyncio
async def test_get_status_none_before_setup_and_populated_after(async_session: AsyncSession, vault: Vault) -> None:
    assert await expedition_scenario_service.get_status(async_session, vault.id) is None

    result = await expedition_scenario_service.setup(
        async_session, vault_id=vault.id, dweller_level=5, duration_hours=8
    )
    status = await expedition_scenario_service.get_status(async_session, vault.id)

    assert status is not None
    assert len(status.explorations) == 1
    entry = status.explorations[0]
    assert entry.exploration_id == result.exploration.id
    assert entry.dweller_name == "Scout Scenario"
    assert entry.dweller_level == 5
    assert entry.status == "active"
    assert entry.open_run_site_id is None
    assert {site.id for site in entry.available_sites} == {"red_rocket", "super_duper_mart"}


@pytest.mark.asyncio
async def test_setup_unknown_vault_raises_not_found(async_session: AsyncSession) -> None:
    with pytest.raises(ResourceNotFoundException):
        await expedition_scenario_service.setup(async_session, vault_id=uuid4(), dweller_level=5, duration_hours=8)


@pytest.mark.asyncio
async def test_setup_default_dweller_special_keeps_checks_differentiated(
    async_session: AsyncSession, vault: Vault
) -> None:
    """Default SPECIAL 5 gives varied check odds (95/85/75), not the 95% cap a high stat pins."""
    result = await expedition_scenario_service.setup(async_session, vault_id=vault.id, dweller_level=5)

    dweller = result.dweller
    assert (dweller.strength, dweller.agility, dweller.endurance) == (5, 5, 5)
    assert (dweller.perception, dweller.charisma, dweller.intelligence, dweller.luck) == (5, 5, 5, 5)


@pytest.mark.asyncio
async def test_setup_special_override_and_clamp(async_session: AsyncSession, vault: Vault) -> None:
    weak = await expedition_scenario_service.setup(async_session, vault_id=vault.id, dweller_level=5, special=1)
    assert weak.dweller.strength == 1
    assert weak.dweller.endurance == 1

    clamped = await expedition_scenario_service.setup(async_session, vault_id=vault.id, dweller_level=5, special=99)
    assert clamped.dweller.strength == 10
