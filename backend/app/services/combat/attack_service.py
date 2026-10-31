"""Shared, transaction-free Arena attacks for arena rooms and expedition scenes."""

from dataclasses import dataclass

from app.schemas.combat import CombatAction, CombatImpact
from app.services.combat.arena_participants import ArenaParticipant
from app.services.combat.weapon_skill import attack_effect, combat_body, weapon_skill


@dataclass
class ResolvedAttack:
    messages: list[str]
    action: CombatAction


def _apply_damage(
    target: ArenaParticipant,
    damage: float,
    carry: dict[str, float],
    *,
    seconds_passed: int,
    cap_multiplier: float,
) -> None:
    capped = min(damage, target.max_health * 0.05 * max(0, seconds_passed) * cap_multiplier)
    carried = carry.get(target.key, 0.0) + capped
    total = int(carried)
    carry[target.key] = carried - total
    target.health = max(0, target.health - total)


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
            damage = attacker.power / 5 * max(0, seconds_passed) * multiplier
            impacts: list[CombatImpact] = []
            messages: list[str] = []
            for target in targets:
                before = target.health
                _apply_damage(target, damage, carry, seconds_passed=seconds_passed, cap_multiplier=multiplier)
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
