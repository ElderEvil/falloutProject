"""Regression guard for the shared attack kernel's default output.

Arena and wasteland sites call ``resolve_attacks`` without a damage multiplier. These
expectations were captured before Combat Zone added the optional keyword, so any default
change is a visible failure rather than a silent balance drift.
"""

from app.services.combat.arena_participants import ArenaParticipant
from app.services.combat.attack_service import resolve_attacks


def _fighter(key: str, *, power: float, health: int, max_health: int) -> ArenaParticipant:
    return ArenaParticipant(
        key=key,
        name=key.upper(),
        short_name=key.upper(),
        power=power,
        health=health,
        max_health=max_health,
    )


def test_default_resolver_output_is_stable_for_a_capped_hit() -> None:
    attacker = _fighter("a1", power=100.0, health=100, max_health=100)
    defender = _fighter("b1", power=80.0, health=100, max_health=100)
    carry: dict[str, float] = {}

    resolved = resolve_attacks([attacker], [defender], 2, set(), carry)

    assert len(resolved) == 1
    action = resolved[0].action
    assert action.actor_id == "a1"
    assert action.targets[0].target_id == "b1"
    assert action.targets[0].damage == 10
    assert action.targets[0].health_before == 100
    assert action.targets[0].health_after == 90
    assert defender.health == 90
    assert carry == {"b1": 0.0}


def test_default_resolver_output_is_stable_for_an_uncapped_hit() -> None:
    attacker = _fighter("a1", power=100.0, health=100, max_health=100)
    defender = _fighter("b1", power=80.0, health=1_000, max_health=1_000)
    carry: dict[str, float] = {}

    resolved = resolve_attacks([attacker], [defender], 2, set(), carry)

    assert resolved[0].action.targets[0].damage == 40
    assert defender.health == 960
    assert carry == {"b1": 0.0}


def test_damage_multiplier_scales_raw_damage_before_the_cap() -> None:
    attacker = _fighter("a1", power=100.0, health=100, max_health=100)
    defender = _fighter("b1", power=80.0, health=1_000, max_health=1_000)
    carry: dict[str, float] = {}

    resolved = resolve_attacks([attacker], [defender], 2, set(), carry, damage_multiplier=1.5)

    assert resolved[0].action.targets[0].damage == 60
    assert defender.health == 940


def test_damage_multiplier_scales_before_the_cap() -> None:
    attacker = _fighter("a1", power=100.0, health=100, max_health=100)
    defender = _fighter("b1", power=80.0, health=100, max_health=100)
    carry: dict[str, float] = {}

    resolved = resolve_attacks([attacker], [defender], 2, set(), carry, damage_multiplier=1.5)

    assert resolved[0].action.targets[0].damage == 10
    assert defender.health == 90
