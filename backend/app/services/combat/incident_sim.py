"""Pure, deterministic incident combat kernel for the balance simulator (no database).
Reuses production's pure helpers (incident_math, damage_reductions, combat_power) — no formula duplication.
No topology: spread is an escalation window; callers supply responders; no team-place earning or auto-equip.
"""

from dataclasses import dataclass, field

from app.core.enums import DamageChannel, HazardTeam, IncidentObjective, IncidentType
from app.models.incident import effects_for_incident_type, get_incident_definition, hazard_team_for
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
    response_grace_seconds: int = 0,
) -> IncidentOutcome:
    """Resolve one incident against the given responders, mirroring incident_round.process_incident.
    FIRE wins at progress >= 1; others at int(progress) >= difficulty*2; no defenders fails after the grace window.
    max_spread_count > 0 adds one duration per spread as an unopposed-spread window.
    """
    threat = incident_math.raider_power(difficulty) if base_raider_power is None else difficulty * base_raider_power
    if threat <= 0:
        raise ValueError("Threat power must be positive")
    effective_threat = incident_math.threat_health(incident_type, threat)
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
    won = False

    if dt <= 0:
        raise ValueError("incident_dt must be positive")
    while True:
        living = [defender for defender in responders if defender.health > 0]
        if not living:
            if elapsed < response_grace_seconds:
                elapsed += dt
                ticks += 1
                continue
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
            containment_threat = max(effective_threat, incident_math.containment_threat_floor(power, dt))
            progress += incident_math.containment_progress(power, containment_threat, dt)
            won = progress >= 1
        else:
            dmg = incident_math.damage_to_dwellers(threat, dt)
            progress += incident_math.damage_to_raiders(power, dt) / effective_threat
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
            break

    return IncidentOutcome(
        resolved=won,
        failed=not won,
        ticks=ticks,
        progress=progress,
        damage_taken=damage_taken,
        deaths=deaths,
        radiation_gained=radiation_gained,
    )
