"""Tests for the expedition-scenario dev/QA provisioning service."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.exploration import ExpeditionRunStatus, ExplorationStatus
from app.models.vault import Vault
from app.schemas.expedition import ExpeditionResolveRequest
from app.services.exploration.expedition import expedition_service
from app.services.exploration.expedition_scenario_service import expedition_scenario_service
from app.services.exploration_service import exploration_service
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
    assert {site.id for site in result.available_sites} == {
        "red_rocket",
        "super_duper_mart",
        "abandoned_campsite",
        "roadside_supply_truck",
        "forgotten_shack",
        "collapsed_subway",
        "rusted_midway",
        "frozen_research_outpost",
        "raider_tollbooth",
    }
    assert result.precleared_site_id is None


@pytest.mark.asyncio
async def test_setup_all_sites_offers_every_site_for_one_scout(async_session: AsyncSession, vault: Vault) -> None:
    result = await expedition_scenario_service.setup(
        async_session, vault_id=vault.id, dweller_level=10, duration_hours=8, all_sites=True
    )

    assert result.exploration.status == ExplorationStatus.ACTIVE
    assert result.exploration.heading_degrees is None
    assert result.exploration.trail == []
    assert result.exploration.time_remaining_seconds() > 0
    assert {site.id for site in result.available_sites} == {
        "red_rocket",
        "super_duper_mart",
        "abandoned_campsite",
        "roadside_supply_truck",
        "forgotten_shack",
        "collapsed_subway",
        "rusted_midway",
        "frozen_research_outpost",
        "raider_tollbooth",
    }


@pytest.mark.asyncio
async def test_all_sites_one_hour_journey_keeps_active_time(async_session: AsyncSession, vault: Vault) -> None:
    result = await expedition_scenario_service.setup(
        async_session, vault_id=vault.id, dweller_level=5, duration_hours=1, all_sites=True
    )

    assert 0 < result.exploration.time_remaining_seconds() <= 30 * 60


@pytest.mark.asyncio
async def test_all_sites_scout_pauses_legacy_journey_clock_on_site_entry(
    async_session: AsyncSession, vault: Vault
) -> None:
    result = await expedition_scenario_service.setup(
        async_session, vault_id=vault.id, dweller_level=10, duration_hours=8, all_sites=True
    )
    exploration = result.exploration
    original_start = datetime.utcnow() - timedelta(hours=5)
    exploration.start_time = original_start
    async_session.add(exploration)
    await async_session.commit()

    await expedition_service.enter_run(async_session, exploration.id, "raider_tollbooth")
    await async_session.refresh(exploration)
    assert exploration.paused_at is not None
    paused_at = exploration.paused_at
    remaining = exploration.time_remaining_seconds()

    await exploration_service.advance(async_session, exploration.id, now=paused_at + timedelta(hours=2))
    await async_session.refresh(exploration)
    assert exploration.paused_at == paused_at
    assert exploration.time_remaining_seconds() == remaining

    exploration_service.resume_from_encounter(exploration, now=paused_at + timedelta(hours=2))
    await async_session.commit()
    await async_session.refresh(exploration)
    assert exploration.paused_at is None
    assert exploration.start_time == original_start + timedelta(hours=2)


@pytest.mark.asyncio
async def test_all_sites_scenario_bypasses_prior_vault_cooldowns_but_not_open_runs(
    async_session: AsyncSession, vault: Vault
) -> None:
    first = await expedition_scenario_service.setup(
        async_session, vault_id=vault.id, dweller_level=10, duration_hours=8, all_sites=True
    )
    cleared = await crud.expedition_run.create_run(
        async_session,
        exploration_id=first.exploration.id,
        vault_id=first.exploration.vault_id,
        site_id="super_duper_mart",
    )
    cleared.status = ExpeditionRunStatus.CLEARED
    cleared.finished_at = datetime.utcnow()
    async_session.add(cleared)
    await crud.expedition_run.create_run(
        async_session,
        exploration_id=first.exploration.id,
        vault_id=first.exploration.vault_id,
        site_id="red_rocket",
    )
    await async_session.commit()

    second = await expedition_scenario_service.setup(
        async_session, vault_id=vault.id, dweller_level=10, duration_hours=8, all_sites=True
    )
    offered = {site.id for site in second.available_sites}
    assert "super_duper_mart" in offered
    assert "red_rocket" not in offered
    room = await expedition_service.enter_run(async_session, second.exploration.id, "super_duper_mart")
    assert room.site_id == "super_duper_mart"


@pytest.mark.asyncio
async def test_all_sites_scenario_can_pay_the_finale_despite_vault_cooldown(
    async_session: AsyncSession, vault: Vault
) -> None:
    first = await expedition_scenario_service.setup(
        async_session, vault_id=vault.id, dweller_level=10, duration_hours=8, all_sites=True
    )
    cleared = await crud.expedition_run.create_run(
        async_session,
        exploration_id=first.exploration.id,
        vault_id=first.exploration.vault_id,
        site_id="super_duper_mart",
    )
    cleared.status = ExpeditionRunStatus.CLEARED
    cleared.finished_at = datetime.utcnow()
    async_session.add(cleared)
    await async_session.commit()

    second = await expedition_scenario_service.setup(
        async_session, vault_id=vault.id, dweller_level=5, duration_hours=8, all_sites=True
    )
    await expedition_service.enter_run(async_session, second.exploration.id, "super_duper_mart")
    run = await crud.expedition_run.get_open_for_exploration(async_session, second.exploration.id)
    assert run is not None
    run.room_cursor = 3
    async_session.add(run)
    await async_session.commit()

    view = await expedition_service.resolve_node(async_session, second.exploration.id, ExpeditionResolveRequest())
    assert view.status == "cleared"
    assert view.finale_paid is True


@pytest.mark.asyncio
async def test_setup_level_four_gates_super_duper_mart(async_session: AsyncSession, vault: Vault) -> None:
    result = await expedition_scenario_service.setup(
        async_session, vault_id=vault.id, dweller_level=4, duration_hours=8
    )

    assert result.dweller.level == 4
    assert [site.id for site in result.available_sites] == [
        "red_rocket",
        "abandoned_campsite",
        "roadside_supply_truck",
        "forgotten_shack",
        "collapsed_subway",
        "rusted_midway",
        "frozen_research_outpost",
        "raider_tollbooth",
    ]


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
    assert {site.id for site in entry.available_sites} == {
        "red_rocket",
        "super_duper_mart",
        "abandoned_campsite",
        "roadside_supply_truck",
        "forgotten_shack",
        "collapsed_subway",
        "rusted_midway",
        "frozen_research_outpost",
        "raider_tollbooth",
    }


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


@pytest.mark.asyncio
async def test_setup_discovered_site_is_playable_on_return_with_real_notification(async_session, vault):
    from app.crud.notification import notification as notification_crud
    from app.services.exploration.expedition import expedition_service
    from app.services.exploration_service import exploration_service

    result = await expedition_scenario_service.setup(
        async_session, vault_id=vault.id, dweller_level=10, discovered_site_id="super_duper_mart"
    )
    exploration = result.exploration
    assert exploration.status == ExplorationStatus.RETURNING
    assert exploration.return_time_remaining_seconds() > 0
    assert exploration.paused_at is None
    assert "super_duper_mart" in {site.id for site in result.available_sites}
    assert any(event.get("site_id") == "super_duper_mart" for event in exploration.events)
    notifications = await notification_crud.get_user_notifications(async_session, vault.user_id)
    assert any((notification.meta_data or {}).get("site_id") == "super_duper_mart" for notification in notifications)
    await exploration_service.advance(async_session, exploration.id)
    room = await expedition_service.enter_run(async_session, exploration.id, "super_duper_mart")
    assert room.site_id == "super_duper_mart"
    assert exploration.paused_at is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("site_id", "level", "preclear", "error"),
    [
        ("unknown", 10, None, "Unknown expedition site"),
        ("super_duper_mart", 1, None, "needs dweller level"),
        ("super_duper_mart", 10, "super_duper_mart", "cannot also be pre-cleared"),
    ],
)
async def test_setup_rejects_invalid_discovery_before_creating_scout(
    async_session, vault, site_id, level, preclear, error
):
    before = await crud.dweller.get_multi_by_vault(async_session, vault.id)
    with pytest.raises(ValueError, match=error):
        await expedition_scenario_service.setup(
            async_session,
            vault_id=vault.id,
            dweller_level=level,
            discovered_site_id=site_id,
            preclear_site_id=preclear,
        )
    after = await crud.dweller.get_multi_by_vault(async_session, vault.id)
    assert {dweller.id for dweller in after} == {dweller.id for dweller in before}


@pytest.mark.asyncio
async def test_setup_reuses_existing_dweller_without_changing_level_or_special(async_session, vault, dweller):
    before = await crud.dweller.get_multi_by_vault(async_session, vault.id)
    original = (dweller.level, dweller.strength, dweller.agility)
    result = await expedition_scenario_service.setup(
        async_session, vault_id=vault.id, dweller_id=dweller.id, discovered_site_id="abandoned_campsite"
    )
    after = await crud.dweller.get_multi_by_vault(async_session, vault.id)
    assert result.dweller.id == dweller.id
    assert len(before) == len(after)
    assert (result.dweller.level, result.dweller.strength, result.dweller.agility) == original
    assert result.exploration.status == ExplorationStatus.RETURNING


@pytest.mark.asyncio
async def test_existing_scenario_dweller_must_belong_to_target_vault(async_session, vault, dweller):
    with pytest.raises(ValueError, match="does not belong"):
        await expedition_scenario_service.setup(async_session, vault_id=uuid4(), dweller_id=dweller.id)
    assert await crud.exploration.get_by_vault(async_session, vault_id=vault.id, active_only=True) == []


@pytest.mark.asyncio
async def test_existing_scenario_dweller_uses_real_level_for_site_gate(async_session, vault, dweller):
    dweller.level = 1
    async_session.add(dweller)
    await async_session.commit()
    with pytest.raises(ValueError, match="needs dweller level"):
        await expedition_scenario_service.setup(
            async_session,
            vault_id=vault.id,
            dweller_id=dweller.id,
            dweller_level=50,
            discovered_site_id="super_duper_mart",
        )
    assert dweller.level == 1
    assert await crud.exploration.get_by_vault(async_session, vault_id=vault.id, active_only=True) == []


@pytest.mark.asyncio
async def test_unknown_existing_scenario_dweller_never_creates_a_replacement(async_session, vault):
    before = {dweller.id for dweller in await crud.dweller.get_multi_by_vault(async_session, vault.id)}
    with pytest.raises(ResourceNotFoundException):
        await expedition_scenario_service.setup(async_session, vault_id=vault.id, dweller_id=uuid4())
    assert {dweller.id for dweller in await crud.dweller.get_multi_by_vault(async_session, vault.id)} == before
