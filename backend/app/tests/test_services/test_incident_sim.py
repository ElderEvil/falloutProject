"""Pure incident combat kernel: split_damage, formula parity, golden incidents, and roster snapshots."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.incident import IncidentType
from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum
from app.schemas.dweller import DwellerCreate
from app.services.combat import incident_math
from app.services.combat.incident_sim import DefenderProfile, SimDefender, resolve_incident
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
