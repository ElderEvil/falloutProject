"""Shared, transaction-free Arena attacks for arena rooms and expedition scenes."""

from dataclasses import dataclass

from app.schemas.combat import CombatAction, CombatImpact
from app.services.combat.arena_participants import ArenaParticipant
from app.services.combat.weapon_skill_service import attack_effect, combat_body, weapon_skill


@dataclass
class ResolvedAttack:
    actor_id: str
    kind: str
    messages: list[str]
    action: CombatAction


def team_damage(team: list[ArenaParticipant], seconds_passed: int) -> float:
    return sum(member.power for member in team if member.health > 0) / 5 * max(0, seconds_passed)


def apply_team_damage(
    defenders: list[ArenaParticipant],
    damage: float,
    carry: dict[str, float],
    *,
    seconds_passed: int | None = None,
    cap_multiplier: float = 1.0,
) -> list[tuple[ArenaParticipant, int]]:
    hits: list[tuple[ArenaParticipant, int]] = []
    pool = damage
    for defender in sorted((p for p in defenders if p.health > 0), key=lambda p: p.health):
        carry_key = defender.key
        capped = (
            min(pool, defender.max_health * 0.05 * max(0, seconds_passed) * cap_multiplier)
            if seconds_passed is not None
            else pool
        )
        carried = carry.get(carry_key, 0.0) + capped
        total = int(carried)
        carry[carry_key] = carried - total
        before = defender.health
        defender.health = max(0, defender.health - total)
        hits.append((defender, total))
        spill = total - min(total, before)
        if defender.health == 0:
            spill += max(0, pool - capped)
        if spill <= 0:
            break
        pool = float(spill)
    return hits


def resolve_attacks(
    attackers: list[ArenaParticipant],
    defenders: list[ArenaParticipant],
    seconds_passed: int,
    queued: set[str],
    carry: dict[str, float],
) -> list[ResolvedAttack]:
    """Resolve one team's turn; consume queued skills only when that fighter attacks."""
    attacks: list[ResolvedAttack] = []
    standing_defenders = [p for p in defenders if p.health > 0]
    if not standing_defenders:
        return attacks
    for index, attacker in enumerate(p for p in attackers if p.health > 0):
        if not any(p.health > 0 for p in standing_defenders):
            break
        chosen = standing_defenders[index % len(standing_defenders)]
        skill = weapon_skill(attacker.dweller) if attacker.key in queued and attacker.dweller else None
        for attack_skill in (skill, None) if skill else (None,):
            living = [p for p in standing_defenders if p.health > 0]
            if not living:
                break
            multiplier = attack_skill.multiplier if attack_skill else 1.0
            targets = living if attack_skill and attack_skill.area else [chosen if chosen.health > 0 else living[0]]
            damage = team_damage([attacker], seconds_passed) * multiplier
            impacts: list[CombatImpact] = []
            messages: list[str] = []
            for target in targets:
                before = target.health
                apply_team_damage([target], damage, carry, seconds_passed=seconds_passed, cap_multiplier=multiplier)
                dealt = before - target.health
                if dealt > 0 or attack_skill:
                    impacts.append(
                        CombatImpact(
                            target_id=target.key,
                            body=combat_body(target.dweller) if target.dweller else target.body,
                            damage=dealt,
                            health_before=before,
                            health_after=target.health,
                        )
                    )
                    verb = f"uses {attack_skill.name} on" if attack_skill else "hits"
                    messages.append(f"{attacker.short_name} {verb} {target.short_name} for {dealt}")
            if messages:
                attacks.append(
                    ResolvedAttack(
                        actor_id=attacker.key,
                        kind="skill" if attack_skill else "hit",
                        messages=messages,
                        action=CombatAction(
                            actor_id=attacker.key,
                            actor_body=combat_body(attacker.dweller) if attacker.dweller else attacker.body,
                            effect=attack_effect(attacker.dweller, attack_skill)
                            if attacker.dweller
                            else attacker.effect,
                            skill=attack_skill.name if attack_skill else None,
                            skill_icon=attack_skill.icon if attack_skill else None,
                            targets=impacts,
                        ),
                    )
                )
        if skill:
            queued.discard(attacker.key)
    return attacks
