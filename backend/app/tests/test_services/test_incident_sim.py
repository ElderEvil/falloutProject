"""Pure incident combat kernel: split_damage, formula parity, golden incidents, and roster snapshots."""

from dataclasses import replace

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import HazardTeam
from app.models.incident import IncidentType
from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum
from app.schemas.dweller import DwellerCreate
from app.services.combat import incident_math
from app.services.combat.incident_sim import DefenderProfile, IncidentOutcome, SimDefender, resolve_incident
from app.services.combat.incident_sim_roster import snapshot_vault_defenders, synthetic_defenders
from app.utils.combat import combat_power
from app.utils.damage_reductions import DamageReductions


def _defender(power: float, health: int = 100) -> SimDefender:
    profile = DefenderProfile(
        label="d",
        power=power,
        max_health=health,
        reductions_physical=DamageReductions(),
        reductions_fire=DamageReductions(),
    )
    return SimDefender(profile=profile, health=health)


def _profiled(
    power: float,
    *,
    health: int = 100,
    radiation: int = 0,
    teams: frozenset[HazardTeam] = frozenset(),
    reductions_physical: DamageReductions | None = None,
    reductions_fire: DamageReductions | None = None,
    reductions_radiation: DamageReductions | None = None,
) -> SimDefender:
    """A defender with explicit team membership and per-channel reductions."""
    profile = DefenderProfile(
        label="d",
        power=power,
        max_health=health,
        reductions_physical=reductions_physical or DamageReductions(),
        reductions_fire=reductions_fire or DamageReductions(),
        reductions_radiation=reductions_radiation or DamageReductions(),
        teams=teams,
    )
    return SimDefender(profile=profile, health=health, radiation=radiation)


def test_team_response_bonus_shortens_containment():
    """Active members of the matching hazard team add +20% response power each."""
    plain = resolve_incident(IncidentType.FIRE, 2, [_profiled(12), _profiled(12)], dt=2)
    team = resolve_incident(
        IncidentType.FIRE,
        2,
        [_profiled(12, teams=frozenset({HazardTeam.FIRE})), _profiled(12, teams=frozenset({HazardTeam.FIRE}))],
        dt=2,
    )
    assert plain.resolved
    assert team.resolved
    # int(24 * 1.4) = 33 power -> 0.66 containment/tick -> win on tick 2, not tick 3.
    assert plain.ticks == 3
    assert team.ticks == 2


def test_team_hazard_resist_reduces_damage():
    """Active members take 20% less on the incident's channel; non-members take full."""
    plain = resolve_incident(IncidentType.FIRE, 2, [_profiled(1000), _profiled(1000)], dt=2)
    team = resolve_incident(
        IncidentType.FIRE,
        2,
        [_profiled(1000, teams=frozenset({HazardTeam.FIRE})), _profiled(1000)],
        dt=2,
    )
    assert plain.resolved
    assert team.resolved
    assert plain.ticks == 1
    assert team.ticks == 1
    # 2 damage split 1/1: the active member resists 1 -> int(1 * 0.8) = 0.
    assert plain.damage_taken == 2
    assert team.damage_taken == 1


def test_team_membership_ignored_for_incidents_without_a_team():
    """Raider (and other) incidents train no team, so team places change nothing."""

    def _run(teams: list[frozenset[HazardTeam]]) -> IncidentOutcome:
        responders = [_profiled(12, teams=team) for team in teams]
        return resolve_incident(IncidentType.RAIDER_ATTACK, 2, responders, dt=2)

    plain = _run([frozenset(), frozenset()])
    tagged = _run([frozenset({HazardTeam.FIRE}), frozenset({HazardTeam.RADIATION})])
    assert (plain.ticks, plain.damage_taken) == (tagged.ticks, tagged.damage_taken)


def test_radscorpion_accumulates_radiation():
    """An irradiating incident adds RAD after physical reduction (production apply_damage)."""
    outcome = resolve_incident(IncidentType.RADSCORPION_ATTACK, 3, [_profiled(1000, health=1000)], dt=2)
    assert outcome.resolved
    assert outcome.ticks == 1
    assert outcome.damage_taken == 6
    # RAD = min(taken - 1, taken // 2) = min(5, 3) = 3.
    assert outcome.radiation_gained == 3


def test_fire_never_adds_radiation():
    outcome = resolve_incident(IncidentType.FIRE, 2, [_profiled(1000, health=1000)], dt=2)
    assert outcome.radiation_gained == 0


def test_radiation_resist_blocks_radiation_gain():
    """A hazmat-equivalent (RAD share 1.0) + active team member gains no RAD."""
    hazmat = DamageReductions(shares=(1.0,))
    outcome = resolve_incident(
        IncidentType.RADSCORPION_ATTACK,
        3,
        [_profiled(1000, health=1000, teams=frozenset({HazardTeam.RADIATION}), reductions_radiation=hazmat)],
        dt=2,
    )
    assert outcome.radiation_gained == 0


def test_radiation_accumulates_per_tick_until_victory():
    """RAD is added at min(taken-1, taken//2) per sub-tick, including the winning round."""
    outcome = resolve_incident(IncidentType.RADSCORPION_ATTACK, 1, [_profiled(25, health=1000)], dt=2)
    assert outcome.resolved
    assert outcome.ticks == 2
    assert outcome.damage_taken == 4
    assert outcome.radiation_gained == 2


def test_radiation_ceiling_clamps_health():
    """A carried RAD pool lowers the health ceiling: health clamps to max(1, max_health - radiation)."""
    responder = _profiled(1000, health=100, radiation=80)
    outcome = resolve_incident(IncidentType.RADSCORPION_ATTACK, 3, [responder], dt=2)
    assert outcome.resolved
    # taken 6 -> 94, rad 80+3=83 -> ceiling max(1, 100-83) = 17.
    assert outcome.damage_taken == 6
    assert responder.radiation == 83
    assert responder.health == 17


def test_split_damage_distributes_base_and_remainder():
    assert incident_math.split_damage(5, 2) == [3, 2]
    assert incident_math.split_damage(10, 3) == [4, 3, 3]
    assert incident_math.split_damage(0, 3) == [0, 0, 0]
    assert incident_math.split_damage(-5, 2) == [0, 0]
    assert incident_math.split_damage(7, 0) == []
    assert incident_math.split_damage(7, -2) == []


def test_kernel_matches_incident_math_non_fire():
    difficulty = 1
    dt = 2
    threat = incident_math.raider_power(difficulty)
    power = 1000.0
    outcome = resolve_incident(IncidentType.RAIDER_ATTACK, difficulty, [_defender(power)], dt=dt)

    dmg = incident_math.damage_to_dwellers(threat, dt)
    expected_progress = incident_math.damage_to_raiders(power, dt) / threat

    assert outcome.resolved
    assert outcome.ticks == 1
    assert outcome.progress == pytest.approx(expected_progress)
    assert outcome.damage_taken == sum(incident_math.split_damage(max(0, int(dmg)), 1))


def test_kernel_matches_incident_math_fire():
    difficulty = 1
    dt = 2
    threat = incident_math.raider_power(difficulty)
    power = 1000.0
    outcome = resolve_incident(IncidentType.FIRE, difficulty, [_defender(power)], dt=dt)

    dmg = incident_math.containment_damage(threat, dt)
    expected_progress = incident_math.containment_progress(power, threat, dt)

    assert outcome.resolved
    assert outcome.ticks == 1
    assert outcome.progress == pytest.approx(expected_progress)
    assert outcome.damage_taken == sum(incident_math.split_damage(max(0, int(dmg)), 1))


def test_golden_non_fire_ticks_to_win():
    # difficulty 2 → threat 20; power 50 → 20 progress per 2s tick → win at int(progress) >= 4.
    outcome = resolve_incident(IncidentType.RAIDER_ATTACK, 2, [_defender(50.0, health=1000)], dt=2)
    assert outcome.resolved
    assert not outcome.failed
    assert outcome.ticks == 4
    assert outcome.progress == pytest.approx(4.0)


def test_golden_fire_ticks_to_win():
    # difficulty 2 → threat 20; power 25 → 0.5 containment per 2s tick → win at progress >= 1.
    outcome = resolve_incident(IncidentType.FIRE, 2, [_defender(25.0, health=1000)], dt=2)
    assert outcome.resolved
    assert not outcome.failed
    assert outcome.ticks == 2
    assert outcome.progress == pytest.approx(1.0)


def test_no_defenders_fails_only_at_duration():
    outcome = resolve_incident(IncidentType.RAIDER_ATTACK, 1, [], dt=2, duration=60)
    assert outcome.failed
    assert not outcome.resolved
    assert outcome.ticks == 30
    assert outcome.damage_taken == 0
    assert outcome.deaths == 0


def test_no_defenders_consumes_full_duration():
    outcome = resolve_incident(IncidentType.FIRE, 1, [], dt=2, duration=30)
    assert outcome.failed
    assert outcome.ticks == 15


def test_outcome_depends_on_responder_power_not_population():
    """Same group power → same win condition, regardless of group size or vault population."""
    six = [_defender(10.0, health=100) for _ in range(6)]
    three = [_defender(20.0, health=100) for _ in range(3)]
    a = resolve_incident(IncidentType.RAIDER_ATTACK, 2, six, dt=2)
    b = resolve_incident(IncidentType.RAIDER_ATTACK, 2, three, dt=2)
    assert a.resolved == b.resolved
    assert a.ticks == b.ticks
    assert a.progress == pytest.approx(b.progress)


def test_synthetic_defenders_are_formula_locked():
    profiles = synthetic_defenders(3, avg_special=4.0, avg_weapon_damage=10.0, avg_level=5)
    assert len(profiles) == 3
    for profile in profiles:
        # unarmed stat weights sum to 0.8; weapon damage and level bonus add on top.
        assert profile.power == pytest.approx(4.0 * 0.8 + 10.0 + 5 * 2)
        assert profile.max_health == 50 + (5 - 1) * 5
        assert profile.reductions_physical.apply(10) == 10
        assert profile.reductions_fire.apply(10) == 10


def test_synthetic_fire_team_wears_catalog_firefighter_suit():
    profiles = synthetic_defenders(
        4, avg_special=4.0, avg_weapon_damage=10.0, avg_level=5, hazard_team=HazardTeam.FIRE, team_size=2
    )
    assert [profile.teams for profile in profiles] == [
        frozenset({HazardTeam.FIRE}),
        frozenset({HazardTeam.FIRE}),
        frozenset(),
        frozenset(),
    ]
    assert profiles[0].reductions_fire.combined_share == pytest.approx(0.5)
    assert profiles[0].reductions_radiation.apply(4) == 4


def test_synthetic_radiation_team_wears_catalog_hazmat_suit():
    profiles = synthetic_defenders(
        2, avg_special=4.0, avg_weapon_damage=10.0, avg_level=5, hazard_team=HazardTeam.RADIATION, team_size=1
    )
    assert profiles[0].teams == frozenset({HazardTeam.RADIATION})
    assert profiles[1].teams == frozenset()
    # Hazmat suit blocks catalog radiation entirely (share 1.0, capped at MAX_RESIST_PCT).
    assert profiles[0].reductions_radiation.apply(4) == 0


def test_synthetic_outfit_count_decouples_gear_from_team_places():
    """The matching outfit can be worn without a place, and a place held without the outfit.

    The four-condition balance playtest needs to isolate the team place from the
    matching gear, so ``outfit_count`` sets who wears the catalog suit
    independently of ``team_size`` (who holds the active place).
    """
    gear_only = synthetic_defenders(
        3,
        avg_special=4.0,
        avg_weapon_damage=10.0,
        avg_level=5,
        hazard_team=HazardTeam.FIRE,
        team_size=0,
        outfit_count=3,
    )
    assert [profile.teams for profile in gear_only] == [frozenset()] * 3
    assert all(profile.reductions_fire.combined_share == pytest.approx(0.5) for profile in gear_only)

    team_only = synthetic_defenders(
        3,
        avg_special=4.0,
        avg_weapon_damage=10.0,
        avg_level=5,
        hazard_team=HazardTeam.FIRE,
        team_size=3,
        outfit_count=0,
    )
    assert [profile.teams for profile in team_only] == [frozenset({HazardTeam.FIRE})] * 3
    assert all(profile.reductions_fire.combined_share == pytest.approx(0.0) for profile in team_only)

    # Omitting outfit_count keeps the Slice 1 default: places and gear go together.
    both = synthetic_defenders(
        3, avg_special=4.0, avg_weapon_damage=10.0, avg_level=5, hazard_team=HazardTeam.FIRE, team_size=3
    )
    assert [profile.teams for profile in both] == [frozenset({HazardTeam.FIRE})] * 3
    assert all(profile.reductions_fire.combined_share == pytest.approx(0.5) for profile in both)


@pytest.mark.asyncio
async def test_snapshot_vault_defenders_only_healthy_adults(async_session: AsyncSession, vault):
    adult = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(
            vault_id=vault.id,
            first_name="Al",
            last_name="Adult",
            gender=GenderEnum.MALE,
            age_group=AgeGroupEnum.ADULT,
            rarity=RarityEnum.COMMON,
            level=5,
            max_health=100,
            health=100,
            radiation=0,
            happiness=50,
            strength=5,
            perception=5,
            endurance=5,
            charisma=5,
            intelligence=5,
            agility=5,
            luck=5,
        ),
    )
    await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(
            vault_id=vault.id,
            first_name="Ch",
            last_name="Child",
            gender=GenderEnum.FEMALE,
            age_group=AgeGroupEnum.CHILD,
            is_adult=False,
            rarity=RarityEnum.COMMON,
            level=1,
            max_health=50,
            health=50,
            radiation=0,
            happiness=50,
            strength=1,
            perception=1,
            endurance=1,
            charisma=1,
            intelligence=1,
            agility=1,
            luck=1,
        ),
    )
    await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(
            vault_id=vault.id,
            first_name="De",
            last_name="Dead",
            gender=GenderEnum.MALE,
            age_group=AgeGroupEnum.ADULT,
            rarity=RarityEnum.COMMON,
            level=5,
            max_health=100,
            health=0,
            radiation=0,
            happiness=50,
            strength=5,
            perception=5,
            endurance=5,
            charisma=5,
            intelligence=5,
            agility=5,
            luck=5,
        ),
    )
    await async_session.commit()

    profiles = await snapshot_vault_defenders(async_session, vault.id)

    assert len(profiles) == 1
    assert profiles[0].label == adult.display_name
    assert profiles[0].max_health == adult.effective_max_health
    loaded = await crud.dweller.get(async_session, adult.id)
    assert profiles[0].power == pytest.approx(combat_power(loaded))


def test_defended_fight_continues_past_no_responder_deadline():
    defender = _defender(1, health=10000)
    outcome = resolve_incident(IncidentType.RAIDER_ATTACK, 2, [defender], dt=2, duration=2)
    assert outcome.resolved
    assert not outcome.failed
    assert outcome.ticks > 1


def test_threat_baseline_changes_combat_damage():
    normal = resolve_incident(IncidentType.RAIDER_ATTACK, 1, [_defender(1000)], dt=2, base_raider_power=10)
    stronger = resolve_incident(IncidentType.RAIDER_ATTACK, 1, [_defender(1000)], dt=2, base_raider_power=20)
    assert stronger.damage_taken > normal.damage_taken
    assert stronger.progress < normal.progress


async def test_snapshot_rejects_unknown_vault(async_session: AsyncSession):
    from uuid import uuid4

    from app.utils.exceptions import ResourceNotFoundException

    with pytest.raises(ResourceNotFoundException):
        await snapshot_vault_defenders(async_session, uuid4())


@pytest.mark.asyncio
async def test_snapshot_defender_pet_reduction_applied_once_per_round(
    async_session: AsyncSession, vault, dweller
) -> None:
    """The snapshot precomputes the pet share once; a round applies it once, never twice.

    Equipped through the real CRUD path, so the snapshot must eager-load the pet
    itself (see ``test_pet_eager_loads``); the round engine then only applies the
    precomputed ``DamageReductions`` — it must not fold the pet share in again.
    """
    pet = await crud.pet.create(async_session, {"name": "Pallas's Cat", "rarity": RarityEnum.LEGENDARY, "value": 500})
    await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)

    profile = (await snapshot_vault_defenders(async_session, vault.id))[0]
    assert profile.reductions_physical.shares == (0.25,)

    # Keep the snapshot's precomputed reductions; raise power only so the round
    # resolves in one tick, making damage_taken exactly one application.
    responders = [SimDefender(profile=replace(profile, power=1000.0), health=100_000)]
    base_raider_power = 200.0
    outcome = resolve_incident(IncidentType.RAIDER_ATTACK, 1, responders, dt=2, base_raider_power=base_raider_power)
    assert outcome.resolved
    assert outcome.ticks == 1

    incoming = max(0, int(incident_math.damage_to_dwellers(1 * base_raider_power, 2)))
    share = incident_math.split_damage(incoming, 1)[0]
    applied_once = profile.reductions_physical.apply(share)
    applied_twice = int(share * (1.0 - 0.25) ** 2)
    assert applied_once != applied_twice, "shares must differ to make the single-application check meaningful"
    assert outcome.damage_taken == applied_once
    assert outcome.damage_taken != applied_twice
