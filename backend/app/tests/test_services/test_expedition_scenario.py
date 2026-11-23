from datetime import timedelta
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import ExpeditionRunStatus, ExplorationStatus, GenderEnum
from app.crud.notification import notification as notification_crud
from app.models.vault import Vault
from app.schemas.expedition import ExpeditionResolveRequest
from app.schemas.vault import VaultNumber
from app.services import catalog_service as data_loader
from app.services.exploration.expedition import expedition_service
from app.services.exploration.expedition_scenario_service import expedition_scenario_service
from app.services.exploration_service import exploration_service
from app.services.vault.scenario_service import vault_scenario_service
from app.services.vault_service import vault_service
from app.utils.exceptions import ResourceNotFoundException
from app.utils.time import utcnow

ALL_SITES = (
    "red_rocket",
    "super_duper_mart",
    "abandoned_campsite",
    "roadside_supply_truck",
    "forgotten_shack",
    "collapsed_subway",
    "rusted_midway",
    "frozen_research_outpost",
    "raider_tollbooth",
    "gloomwater_bog",
    "gloomwater_bog_night",
    "outskirts_interchange",
)
SINGLE_SCENE_SITES = tuple(site for site in ALL_SITES if site not in ("red_rocket", "super_duper_mart"))
EIGHT_HOURS = {"duration_hours": 8}


async def _save(db, *objs):
    for obj in objs:
        db.add(obj)
    await db.commit()


async def _setup(db: AsyncSession, vault: Vault, **overrides):
    return await expedition_scenario_service.setup(db, vault_id=vault.id, **overrides)


async def _multi(db: AsyncSession, vault: Vault, **overrides):
    overrides.setdefault("duration_hours", 8)
    return await expedition_scenario_service.setup_multi(db, vault_id=vault.id, **overrides)


async def _mark_run(db: AsyncSession, exploration, site_id: str, status=ExpeditionRunStatus.CLEARED):
    run = await crud.expedition_run.create_run(
        db, exploration_id=exploration.id, vault_id=exploration.vault_id, site_id=site_id
    )
    run.status = status
    run.finished_at = utcnow()
    db.add(run)
    await db.commit()
    return run


def _ids(result) -> set[str]:
    return {site.id for site in result.available_sites}


class TestExpeditionScenario:
    pytestmark = pytest.mark.asyncio

    async def test_setup_creates_level_five_dweller_on_active_exploration(
        self, async_session: AsyncSession, vault: Vault
    ):
        result = await _setup(async_session, vault, dweller_level=5, duration_hours=8)
        assert result.created_vault is False
        assert result.vault.id == vault.id
        assert result.dweller.level == 5
        assert result.dweller.display_name == "Scout Scenario"
        assert result.exploration.status == ExplorationStatus.ACTIVE
        assert result.exploration.duration == 8
        assert _ids(result) == set(ALL_SITES)
        assert result.precleared_site_id is None

    async def test_setup_all_sites_offers_single_scene_sites_for_one_scout(
        self, async_session: AsyncSession, vault: Vault
    ):
        result = await _setup(async_session, vault, dweller_level=10, all_sites=True, **EIGHT_HOURS)
        assert result.exploration.status == ExplorationStatus.ACTIVE
        assert result.exploration.heading_degrees is None
        assert result.exploration.trail == []
        assert result.exploration.time_remaining_seconds() > 0
        assert _ids(result) == set(SINGLE_SCENE_SITES)

    async def test_setup_all_sites_can_include_multi_room_when_explicitly_enabled(self, async_session, vault):
        result = await _setup(
            async_session, vault, dweller_level=10, all_sites=True, single_scene_only=False, **EIGHT_HOURS
        )
        assert _ids(result) == set(ALL_SITES)

    async def test_all_sites_one_hour_journey_keeps_active_time(self, async_session: AsyncSession, vault: Vault):
        result = await _setup(async_session, vault, dweller_level=5, duration_hours=1, all_sites=True)
        assert 0 < result.exploration.time_remaining_seconds() <= 30 * 60

    async def test_all_sites_scout_pauses_legacy_journey_clock_on_site_entry(
        self, async_session: AsyncSession, vault: Vault
    ):
        result = await _setup(async_session, vault, dweller_level=10, all_sites=True, **EIGHT_HOURS)
        exploration = result.exploration
        original_start = utcnow() - timedelta(hours=5)
        exploration.start_time = original_start
        await _save(async_session, exploration)
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

    async def test_all_sites_scenario_bypasses_prior_vault_cooldowns_but_not_open_runs(self, async_session, vault):
        first = await _setup(
            async_session, vault, dweller_level=10, all_sites=True, single_scene_only=False, **EIGHT_HOURS
        )
        await _mark_run(async_session, first.exploration, "super_duper_mart")
        await crud.expedition_run.create_run(
            async_session,
            exploration_id=first.exploration.id,
            vault_id=first.exploration.vault_id,
            site_id="red_rocket",
        )
        await async_session.commit()
        second = await _setup(
            async_session, vault, dweller_level=10, all_sites=True, single_scene_only=False, **EIGHT_HOURS
        )
        offered = _ids(second)
        assert "super_duper_mart" in offered
        assert "red_rocket" not in offered
        room = await expedition_service.enter_run(async_session, second.exploration.id, "super_duper_mart")
        assert room.site_id == "super_duper_mart"

    async def test_all_sites_scenario_can_pay_the_finale_despite_vault_cooldown(
        self, async_session: AsyncSession, vault: Vault
    ):
        first = await _setup(
            async_session, vault, dweller_level=10, all_sites=True, single_scene_only=False, **EIGHT_HOURS
        )
        await _mark_run(async_session, first.exploration, "super_duper_mart")
        second = await _setup(
            async_session, vault, dweller_level=5, all_sites=True, single_scene_only=False, **EIGHT_HOURS
        )
        await expedition_service.enter_run(async_session, second.exploration.id, "super_duper_mart")
        run = await crud.expedition_run.get_open_for_exploration(async_session, second.exploration.id)
        assert run is not None
        run.room_cursor = 3
        await _save(async_session, run)
        view = await expedition_service.resolve_node(async_session, second.exploration.id, ExpeditionResolveRequest())
        assert view.status == "cleared"
        assert view.finale_paid is True

    async def test_setup_level_four_gates_super_duper_mart(self, async_session: AsyncSession, vault: Vault):
        result = await _setup(async_session, vault, dweller_level=4, **EIGHT_HOURS)
        assert result.dweller.level == 4
        assert [site.id for site in result.available_sites] == [s for s in ALL_SITES if s != "super_duper_mart"]

    async def test_setup_preclear_hides_site_from_picker(self, async_session: AsyncSession, vault: Vault):
        result = await _setup(async_session, vault, dweller_level=5, preclear_site_id="red_rocket", **EIGHT_HOURS)
        assert result.precleared_site_id == "red_rocket"
        assert "red_rocket" not in _ids(result)
        assert "super_duper_mart" in _ids(result)

    async def test_setup_unknown_preclear_site_raises(self, async_session: AsyncSession, vault: Vault):
        with pytest.raises(ValueError, match="Unknown expedition site"):
            await _setup(async_session, vault, dweller_level=5, preclear_site_id="nope", **EIGHT_HOURS)
        assert await crud.exploration.get_by_vault(async_session, vault_id=vault.id, active_only=True) == []

    async def test_get_status_none_before_setup_and_populated_after(self, async_session: AsyncSession, vault: Vault):
        assert await expedition_scenario_service.get_status(async_session, vault.id) is None
        result = await _setup(async_session, vault, dweller_level=5, **EIGHT_HOURS)
        status = await expedition_scenario_service.get_status(async_session, vault.id)
        assert status is not None
        assert len(status.explorations) == 1
        entry = status.explorations[0]
        assert entry.exploration_id == result.exploration.id
        assert entry.dweller_name == "Scout Scenario"
        assert entry.dweller_level == 5
        assert entry.status == "active"
        assert entry.open_run_site_id is None
        assert {site.id for site in entry.available_sites} == set(ALL_SITES)

    async def test_setup_unknown_vault_raises_not_found(self, async_session: AsyncSession):
        with pytest.raises(ResourceNotFoundException):
            await expedition_scenario_service.setup(async_session, vault_id=uuid4(), dweller_level=5, duration_hours=8)

    async def test_setup_default_dweller_special_keeps_checks_differentiated(
        self, async_session: AsyncSession, vault: Vault
    ):
        result = await _setup(async_session, vault, dweller_level=5)
        dweller = result.dweller
        assert (dweller.strength, dweller.agility, dweller.endurance) == (5, 5, 5)
        assert (dweller.perception, dweller.charisma, dweller.intelligence, dweller.luck) == (5, 5, 5, 5)

    async def test_setup_special_override_and_clamp(self, async_session: AsyncSession, vault: Vault):
        weak = await _setup(async_session, vault, dweller_level=5, special=1)
        assert weak.dweller.strength == 1
        assert weak.dweller.endurance == 1
        clamped = await _setup(async_session, vault, dweller_level=5, special=99)
        assert clamped.dweller.strength == 10

    async def test_setup_discovered_site_is_playable_on_return_with_real_notification(self, async_session, vault):
        result = await _setup(async_session, vault, dweller_level=10, discovered_site_id="super_duper_mart")
        exploration = result.exploration
        assert exploration.status == ExplorationStatus.RETURNING
        assert exploration.return_time_remaining_seconds() > 0
        assert exploration.paused_at is None
        assert "super_duper_mart" in _ids(result)
        assert any(event.get("site_id") == "super_duper_mart" for event in exploration.events)
        notifications = await notification_crud.get_user_notifications(async_session, vault.user_id)
        assert any((n.meta_data or {}).get("site_id") == "super_duper_mart" for n in notifications)
        await exploration_service.advance(async_session, exploration.id)
        room = await expedition_service.enter_run(async_session, exploration.id, "super_duper_mart")
        assert room.site_id == "super_duper_mart"
        assert exploration.paused_at is not None

    @pytest.mark.parametrize(
        ("site_id", "level", "preclear", "error"),
        [
            ("unknown", 10, None, "Unknown expedition site"),
            ("super_duper_mart", 1, None, "needs dweller level"),
            ("super_duper_mart", 10, "super_duper_mart", "cannot also be pre-cleared"),
        ],
    )
    async def test_setup_rejects_invalid_discovery_before_creating_scout(
        self, async_session, vault, site_id, level, preclear, error
    ):
        before = await crud.dweller.get_multi_by_vault(async_session, vault.id)
        with pytest.raises(ValueError, match=error):
            await _setup(
                async_session, vault, dweller_level=level, discovered_site_id=site_id, preclear_site_id=preclear
            )
        after = await crud.dweller.get_multi_by_vault(async_session, vault.id)
        assert {dweller.id for dweller in after} == {dweller.id for dweller in before}

    async def test_setup_reuses_existing_dweller_without_changing_level_or_special(self, async_session, vault, dweller):
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

    async def test_existing_scenario_dweller_must_belong_to_target_vault(self, async_session, vault, dweller):
        with pytest.raises(ValueError, match="does not belong"):
            await expedition_scenario_service.setup(async_session, vault_id=uuid4(), dweller_id=dweller.id)
        assert await crud.exploration.get_by_vault(async_session, vault_id=vault.id, active_only=True) == []

    async def test_existing_scenario_dweller_uses_real_level_for_site_gate(self, async_session, vault, dweller):
        dweller.level = 1
        await _save(async_session, dweller)
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

    async def test_unknown_existing_scenario_dweller_never_creates_a_replacement(self, async_session, vault):
        before = {dweller.id for dweller in await crud.dweller.get_multi_by_vault(async_session, vault.id)}
        with pytest.raises(ResourceNotFoundException):
            await expedition_scenario_service.setup(async_session, vault_id=vault.id, dweller_id=uuid4())
        assert {dweller.id for dweller in await crud.dweller.get_multi_by_vault(async_session, vault.id)} == before

    async def test_setup_multi_seeds_named_dwellers_with_one_site_each(self, async_session: AsyncSession, vault: Vault):
        site_ids = ["gloomwater_bog", "gloomwater_bog_night", "outskirts_interchange"]
        result = await _multi(async_session, vault, dwellers=3, dweller_level=5, site_ids=site_ids)
        assert len(result.entries) == 3
        assert [entry.dweller.display_name for entry in result.entries] == ["Ada Voss", "Bram Cole", "Cora Reyes"]
        assert len({entry.dweller.id for entry in result.entries}) == 3
        assert [entry.dweller.gender for entry in result.entries] == [
            GenderEnum.FEMALE,
            GenderEnum.MALE,
            GenderEnum.FEMALE,
        ]
        assert [entry.dweller.strength for entry in result.entries] == [6, 5, 4]
        stat_lines = {
            (
                entry.dweller.strength,
                entry.dweller.perception,
                entry.dweller.endurance,
                entry.dweller.charisma,
                entry.dweller.intelligence,
                entry.dweller.agility,
                entry.dweller.luck,
            )
            for entry in result.entries
        }
        assert len(stat_lines) == 3
        assert "Female" in (result.entries[0].dweller.image_url or "")
        assert "Male" in (result.entries[1].dweller.image_url or "")
        assert "Female" in (result.entries[2].dweller.image_url or "")
        for entry, site_id in zip(result.entries, site_ids, strict=True):
            fresh = await crud.exploration.get(async_session, entry.exploration.id)
            assert fresh is not None
            assert fresh.status == ExplorationStatus.ACTIVE
            assert entry.discovered_site_id == site_id
            assert site_id in _ids(entry)
            assert any(event.get("site_id") == site_id for event in fresh.events)
            assert fresh.time_remaining_seconds() > 0

    async def test_setup_multi_reuses_or_creates_vault_one(self, async_session: AsyncSession, superuser):
        result = await expedition_scenario_service.setup_multi(
            async_session, user_email=superuser.email, vault_number=1, dwellers=3, dweller_level=5, duration_hours=8
        )
        assert result.vault.number == 1
        assert len(result.entries) == 3
        assert all(entry.vault.id == result.vault.id for entry in result.entries)

    async def test_setup_multi_recreates_vault_one_before_seeding(self, async_session: AsyncSession, superuser):
        old_vault = await vault_service.initiate_vault(
            async_session, obj_in=VaultNumber(number=1, boosted=False), user_id=superuser.id
        )
        old_vault_id = old_vault.id
        result = await expedition_scenario_service.setup_multi(
            async_session,
            user_email=superuser.email,
            vault_number=1,
            dwellers=3,
            dweller_level=5,
            duration_hours=8,
            recreate=True,
        )
        assert result.created_vault is True
        assert result.vault.id != old_vault_id
        assert result.vault.number == 1
        assert len(result.entries) == 3
        await async_session.refresh(old_vault)
        assert old_vault.is_deleted is True

    async def test_setup_multi_defaults_to_one_dweller_per_site(self, async_session: AsyncSession, vault: Vault):
        result = await _multi(async_session, vault, dweller_level=10)
        expected_sites = [site.id for site in data_loader.load_expedition_sites() if not site.scenario_only]
        assert len(result.entries) == len(expected_sites)
        assert len({entry.dweller.id for entry in result.entries}) == len(expected_sites)
        assert len({entry.dweller.display_name for entry in result.entries}) == len(expected_sites)
        assert [entry.discovered_site_id for entry in result.entries] == expected_sites
        assert all(entry.exploration.status == ExplorationStatus.ACTIVE for entry in result.entries)

    async def test_setup_multi_can_keep_legacy_one_site_pickers(self, async_session: AsyncSession, vault: Vault):
        site_ids = ["gloomwater_bog", "outskirts_interchange"]
        result = await _multi(async_session, vault, dwellers=2, site_ids=site_ids, discover=False)
        for entry, site_id in zip(result.entries, site_ids, strict=True):
            assert entry.discovered_site_id is None
            assert [site.id for site in entry.available_sites] == [site_id]

    async def test_setup_multi_rejects_more_dwellers_than_sites(self, async_session: AsyncSession, vault: Vault):
        with pytest.raises(ValueError, match="own site"):
            await _multi(async_session, vault, dwellers=2, site_ids=["gloomwater_bog"])

    async def test_vault_1_scenario_scouts_every_site_and_fits_capacity(
        self, async_session: AsyncSession, vault: Vault
    ):
        scenario = vault_scenario_service.get("vault_1_test")
        assert scenario is not None
        await vault_scenario_service.seed(async_session, vault, scenario)
        await async_session.refresh(vault)
        dwellers = await crud.dweller.get_multi_by_vault(async_session, vault.id, limit=100)
        explorations = await crud.exploration.get_by_vault(async_session, vault_id=vault.id, active_only=True)
        expected_sites = {site.id for site in data_loader.load_expedition_sites() if not site.scenario_only}
        assert len(explorations) == len(expected_sites)
        assert vault.population_max is not None
        assert vault.population_max >= len(dwellers)
        for exploration in explorations:
            assert exploration.status == ExplorationStatus.ACTIVE
            assert any(event.get("event") == "site_found" for event in exploration.events)
        scout_ids = {exploration.dweller_id for exploration in explorations}
        scouts = [dweller for dweller in dwellers if dweller.id in scout_ids]
        assert {dweller.level for dweller in scouts} == {5, 10, 15, 20}
        weapons = [await crud.weapon.get_equipped(async_session, dweller.id) for dweller in scouts]
        assert any(weapon is None for weapon in weapons)
        assert {weapon.weapon_type.value for weapon in weapons if weapon is not None} == {
            "melee",
            "gun",
            "energy",
            "heavy",
        }
        pets = [await crud.pet.get_equipped(async_session, dweller.id) for dweller in scouts]
        assert any(pet is not None for pet in pets)
        assert sum(pet is not None for pet in pets) < len(scouts) // 2

    async def test_setup_multi_variety_spans_levels_weapons_and_sparse_pets(
        self, async_session: AsyncSession, vault: Vault
    ):
        result = await _multi(async_session, vault, dwellers=8, dweller_level=5, variety=True)
        assert [entry.dweller.level for entry in result.entries] == [5, 10, 15, 20, 5, 10, 15, 20]
        weapons = [await crud.weapon.get_equipped(async_session, entry.dweller.id) for entry in result.entries]
        assert [weapon.weapon_type.value if weapon else None for weapon in weapons] == [
            None,
            "melee",
            "gun",
            None,
            "energy",
            "heavy",
            None,
            "melee",
        ]
        pets = [await crud.pet.get_equipped(async_session, entry.dweller.id) for entry in result.entries]
        assert [pet is not None for pet in pets] == [True, False, False, False, True, False, False, False]
        assert result.entries[3].loadout == "unarmed"

    async def test_setup_multi_variety_does_not_equip_when_departure_fails(self, async_session, vault, monkeypatch):
        async def fail_send_dweller(*args: object, **kwargs: object) -> None:
            raise RuntimeError("departure failed")

        monkeypatch.setattr(exploration_service, "send_dweller", fail_send_dweller)
        with pytest.raises(RuntimeError, match="departure failed"):
            await _multi(async_session, vault, dwellers=2, dweller_level=5, variety=True)
        dwellers = await crud.dweller.get_all_in_vault(async_session, vault.id)
        assert dwellers
        assert [await crud.weapon.get_equipped(async_session, d.id) for d in dwellers] == [None] * len(dwellers)
        assert [await crud.pet.get_equipped(async_session, d.id) for d in dwellers] == [None] * len(dwellers)
