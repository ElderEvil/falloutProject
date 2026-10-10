"""Pure, deterministic incident combat kernel mirroring the production round engine.

``resolve_incident`` reproduces the combat loop of
``app.services.combat.incident_round.process_incident`` — the same threat,
damage, suppression, damage-split and victory formulas — but synchronous,
deterministic and roster-driven, so the balance simulator can run thousands of
incidents without a database.

One intentional divergence from production: the hazard-team response bonus
(``TEAM_RESPONSE_BONUS``) and radiation accumulation are NOT modeled. Responders
fight with their raw ``combat_power`` and take damage on the incident's channel
only; there is no team ledger, no outfit auto-equip, and no RAD gain.
"""

from dataclasses import dataclass

from app.core.enums import DamageChannel
from app.models.incident import IncidentObjective, IncidentType, effects_for_incident_type, get_incident_definition
from app.services.combat import incident_math
from app.utils.damage_reductions import DamageReductions


@dataclass(frozen=True)
class DefenderProfile:
    """Static combat inputs for one defender, independent of current health."""

    label: str
    power: float
    max_health: int
    reductions_physical: DamageReductions
    reductions_fire: DamageReductions


@dataclass
class SimDefender:
    """A defender with mutable current health; health 0 means dead."""

    profile: DefenderProfile
    health: int


@dataclass(frozen=True)
class IncidentOutcome:
    """The terminal state of one resolved incident."""

    resolved: bool
    failed: bool
    ticks: int
    progress: float
    damage_taken: int
    deaths: int


def resolve_incident(
    incident_type: IncidentType,
    difficulty: int,
    responders: list[SimDefender],
    *,
    dt: int,
    duration: int = 60,
    max_spread_count: int = 0,
) -> IncidentOutcome:
    """Resolve one incident to completion against the given responders.

    Mirrors ``incident_round.process_incident``: each sub-tick of ``dt`` seconds
    deals ``incident_math`` damage to the living responders (split evenly, the
    first ones take the remainder) and accumulates suppression progress. FIRE
    wins at ``progress >= 1``; every other type wins at
    ``int(progress) >= difficulty * 2``. With no living responders the sub-ticks
    are consumed without damage until the duration elapses, then the incident
    fails. ``max_spread_count`` is accepted for signature parity with the
    production engine; when > 0 it extends the effective duration (one extra
    ``duration`` per spread), otherwise the default path fails at ``duration``.
    """
    threat = incident_math.raider_power(difficulty)
    effects = effects_for_incident_type(incident_type)
    channel = effects.damage
    effective_duration = duration * (1 + max_spread_count)

    progress = 0.0
    damage_taken = 0
    deaths = 0
    elapsed = 0
    ticks = 0

    if dt <= 0:
        raise ValueError("incident_dt must be positive")
    while True:
        living = [defender for defender in responders if defender.health > 0]
        if not living and elapsed >= effective_duration:
            break
        power = sum(defender.profile.power for defender in living)

        if get_incident_definition(incident_type).objective == IncidentObjective.CONTAIN:
            dmg = incident_math.containment_damage(threat, dt)
            progress += incident_math.containment_progress(power, threat, dt)
            won = progress >= 1
        else:
            dmg = incident_math.damage_to_dwellers(threat, dt)
            progress += incident_math.damage_to_raiders(power, dt) / threat
            won = int(progress) >= difficulty * 2

        if living:
            split = incident_math.split_damage(max(0, int(dmg)), len(living))
            for defender, share in zip(living, split, strict=True):
                reductions = (
                    defender.profile.reductions_fire
                    if channel is DamageChannel.FIRE
                    else defender.profile.reductions_physical
                )
                taken = reductions.apply(share)
                if taken <= 0:
                    continue
                damage_taken += taken
                new_health = max(0, defender.health - taken)
                if new_health <= 0 and defender.health > 0:
                    deaths += 1
                defender.health = new_health

        elapsed += dt
        ticks += 1

        if won:
            return IncidentOutcome(
                resolved=True, failed=False, ticks=ticks, progress=progress, damage_taken=damage_taken, deaths=deaths
            )

    return IncidentOutcome(
        resolved=False, failed=True, ticks=ticks, progress=progress, damage_taken=damage_taken, deaths=deaths
    )
