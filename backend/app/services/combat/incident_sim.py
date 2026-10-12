"""Pure, deterministic incident combat kernel mirroring the production round engine.

``resolve_incident`` reproduces the combat loop of
``app.services.combat.incident_round.process_incident`` — the same threat,
damage, suppression, damage-split, hazard-team response, radiation and victory
formulas — but synchronous, deterministic and roster-driven, so the balance
simulator can run thousands of incidents without a database. It calls the same
pure helpers production uses (``incident_math``, ``damage_reductions``,
``combat_power``) rather than duplicating any formula.

Simulation limitations: without room topology, unopposed spread is modeled as an
extended escalation window, not adjacent-room spawning. Responders are supplied
by the caller, so the simulator's roster choice (not production's room occupancy
plus auto-dispatch) decides who fights. Team place earning and outfit
auto-equip are not simulated: a defender is configured with the team places and
outfit reductions it is assumed to already hold.
"""

from dataclasses import dataclass, field

from app.core.enums import DamageChannel, HazardTeam
from app.models.incident import (
    IncidentObjective,
    IncidentType,
    effects_for_incident_type,
    get_incident_definition,
    hazard_team_for,
)
from app.services.combat import incident_math
from app.services.hazard_team_service import TEAM_HAZARD_RESIST, TEAM_RESPONSE_BONUS
from app.utils.damage_reductions import DamageReductions


@dataclass(frozen=True)
class DefenderProfile:
    """Static combat inputs for one defender, independent of current health."""

    label: str
    power: float
    max_health: int
    reductions_physical: DamageReductions
    reductions_fire: DamageReductions
    reductions_radiation: DamageReductions = field(default_factory=DamageReductions)
    teams: frozenset[HazardTeam] = frozenset()


@dataclass
class SimDefender:
    """A defender with mutable health and radiation; health 0 means dead."""

    profile: DefenderProfile
    health: int
    radiation: int = 0


@dataclass(frozen=True)
class IncidentOutcome:
    """The terminal state of one resolved incident."""

    resolved: bool
    failed: bool
    ticks: int
    progress: float
    damage_taken: int
    deaths: int
    radiation_gained: int = 0


def _with_team(reductions: DamageReductions, team_share: float) -> DamageReductions:
    """Fold the active hazard-team share into a precomputed reduction set (production apply_damage)."""
    if team_share <= 0:
        return reductions
    return DamageReductions(shares=(*reductions.shares, team_share), immune=reductions.immune)


def resolve_incident(
    incident_type: IncidentType,
    difficulty: int,
    responders: list[SimDefender],
    *,
    dt: int,
    duration: int = 60,
    max_spread_count: int = 0,
    base_raider_power: float | None = None,
) -> IncidentOutcome:
    """Resolve one incident to completion against the given responders.

    Mirrors ``incident_round.process_incident``: active members of the incident's
    matching hazard team add ``TEAM_RESPONSE_BONUS`` power each and resist
    ``TEAM_HAZARD_RESIST`` on the incident's channel; each sub-tick of ``dt``
    seconds deals ``incident_math`` damage to the living responders (split
    evenly, the first ones take the remainder), accumulates suppression progress,
    and — for irradiating incidents — adds ``min(taken-1, taken//2)`` RAD after
    outfit/team reduction, clamping health to ``max(1, max_health - radiation)``.
    FIRE wins at ``progress >= 1``; every other type wins at
    ``int(progress) >= difficulty * 2``. With no living responders and spread
    disabled the incident fails on that round, like production's
    no-defender outcome — it does not burn sub-ticks to the duration.
    ``max_spread_count`` is accepted for signature parity with the
    production engine; when > 0 it extends the effective duration (one extra
    ``duration`` per spread) as an unopposed-spread window, otherwise the
    default path fails at ``duration`` only while spread could still occur.
    """
    threat = incident_math.raider_power(difficulty) if base_raider_power is None else difficulty * base_raider_power
    if threat <= 0:
        raise ValueError("Threat power must be positive")
    effects = effects_for_incident_type(incident_type)
    channel = effects.damage
    objective = get_incident_definition(incident_type).objective
    hazard_team = hazard_team_for(incident_type)
    effective_duration = duration * (1 + max_spread_count)

    progress = 0.0
    damage_taken = 0
    deaths = 0
    radiation_gained = 0
    elapsed = 0
    ticks = 0

    if dt <= 0:
        raise ValueError("incident_dt must be positive")
    while True:
        living = [defender for defender in responders if defender.health > 0]
        if not living:
            if max_spread_count == 0:
                elapsed += dt
                ticks += 1
                break
            if elapsed >= effective_duration:
                break
        active_count = sum(
            1 for defender in living if hazard_team is not None and hazard_team in defender.profile.teams
        )
        raw_power = sum(defender.profile.power for defender in living)
        power = int(raw_power * (1 + TEAM_RESPONSE_BONUS * active_count)) if active_count else raw_power

        if objective == IncidentObjective.CONTAIN:
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
                is_active = hazard_team is not None and hazard_team in defender.profile.teams
                team_share = TEAM_HAZARD_RESIST if is_active else 0.0
                base_reductions = (
                    defender.profile.reductions_fire
                    if channel is DamageChannel.FIRE
                    else defender.profile.reductions_physical
                )
                taken = _with_team(base_reductions, team_share).apply(share)
                if taken <= 0:
                    continue
                damage_taken += taken
                new_health = max(0, defender.health - taken)

                if effects.irradiates and taken > 1:
                    radiation_damage = min(taken - 1, taken // 2)
                    rad_applied = _with_team(defender.profile.reductions_radiation, team_share).apply(radiation_damage)
                    if rad_applied > 0:
                        defender.radiation = min(defender.profile.max_health, defender.radiation + rad_applied)
                        radiation_gained += rad_applied

                new_health = min(new_health, max(1, defender.profile.max_health - defender.radiation))
                if new_health <= 0 and defender.health > 0:
                    deaths += 1
                defender.health = new_health

        elapsed += dt
        ticks += 1

        if won:
            return IncidentOutcome(
                resolved=True,
                failed=False,
                ticks=ticks,
                progress=progress,
                damage_taken=damage_taken,
                deaths=deaths,
                radiation_gained=radiation_gained,
            )

    return IncidentOutcome(
        resolved=False,
        failed=True,
        ticks=ticks,
        progress=progress,
        damage_taken=damage_taken,
        deaths=deaths,
        radiation_gained=radiation_gained,
    )
