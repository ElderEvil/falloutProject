"""Arena combat in one authored site scene. The expedition service owns all writes/commits."""

from typing import Literal

from app.models.dweller import Dweller
from app.schemas.expedition import SiteCombatView, SiteDefinition
from app.services.catalog_service import list_site_enemies
from app.services.combat.arena_participants import (
    ArenaParticipant,
    catalog_participants,
    charge_per_second,
    fighter_view,
    participant_from_dweller,
)
from app.services.combat.attack_service import resolve_attacks
from app.services.combat.weapon_skill_service import MAX_CHARGE
from app.utils.exceptions import ValidationException

TURN_SECONDS = 2


def initial_combat(site: SiteDefinition) -> dict:
    catalog = {entry["key"]: entry for entry in list_site_enemies()}
    opponents = []
    if site.encounter is None:
        raise ValidationException(f"Missing encounter in {site.id}")
    for spec in site.encounter.node.enemies:
        entry = catalog.get(spec.arena_key)
        if entry is None:
            raise ValidationException(f"Unknown scene enemy {spec.arena_key!r} in {site.id}")
        hp = max(1, round(entry["max_hp"] * site.enemy_health_scale))
        opponents.append(
            {
                **entry,
                "power": entry["power"] * site.enemy_power_scale,
                "max_hp": hp,
                "hp": hp,
            }
        )
    if not opponents:
        raise ValidationException(f"Combat encounter {site.id} needs an enemy")
    return {
        "round": 0,
        "next_attack_team": "A",
        "opponents": opponents,
        "charge": 0,
        "carry": {},
        "events": [{"id": "0", "message": "Encounter ready", "action": None}],
    }


def _opponents(state: dict) -> list[ArenaParticipant]:
    opponents = catalog_participants(state["opponents"])
    for enemy, entry in zip(opponents, state["opponents"], strict=True):
        enemy.body = (
            "feral" if entry["key"] == "feral-ghoul" else "mutant" if entry["key"] == "super-mutant" else "human"
        )
        enemy.effect = "shot" if entry["key"] in {"raider", "super-mutant"} else "strike"
    return opponents


def combat_view(state: dict, dweller: Dweller) -> SiteCombatView:
    fighter = participant_from_dweller(dweller)
    return SiteCombatView(
        round=state["round"],
        next_attack_team=state["next_attack_team"],
        fighters=[fighter_view(fighter, int(state["charge"])), *[fighter_view(enemy) for enemy in _opponents(state)]],
        events=state["events"],
    )


def encounter_threat(site: SiteDefinition, dweller: Dweller) -> Literal["low", "moderate", "high"]:
    """Estimate health pressure from actual equipment/current HP, using the shared arena damage cap."""
    player = participant_from_dweller(dweller)
    enemies = _opponents(initial_combat(site))
    expected = 0.0
    for index, enemy in enumerate(enemies):
        turns = enemy.health / max(0.1, min(player.power / 5, enemy.max_health * 0.05))
        expected += turns * sum(min(p.power / 5, player.max_health * 0.05) for p in enemies[index:])
    ratio = expected / max(1, player.health)
    return "low" if ratio < 0.5 else "moderate" if ratio < 0.9 else "high"


def resolve_turn(state: dict, dweller: Dweller, *, use_skill: bool) -> tuple[dict, bool, bool, int]:
    """Advance one alternating team turn; HP/skill input always comes from persisted server state."""
    if use_skill and (state["charge"] < MAX_CHARGE or state["next_attack_team"] != "A"):
        raise ValidationException("The active skill is not ready on this turn")
    player, enemies = participant_from_dweller(dweller), _opponents(state)
    before = player.health
    queued = {player.key} if use_skill else set()
    carry = dict(state["carry"])
    attackers, defenders = ([player], enemies) if state["next_attack_team"] == "A" else (enemies, [player])
    attacks = resolve_attacks(attackers, defenders, TURN_SECONDS, queued, carry)
    turn = state["round"] + 1
    events = [
        *state["events"],
        *[
            {
                "id": f"{turn}:{index}",
                "message": " · ".join(attack.messages),
                "action": attack.action.model_dump(),
            }
            for index, attack in enumerate(attacks)
        ],
    ]
    won, lost = all(enemy.health <= 0 for enemy in enemies), player.health <= 0
    # The fight may reach 0, but the actual dweller is never killed by a scene encounter.
    dweller.health = max(1, player.health)
    state = {
        "round": turn,
        "next_attack_team": "B" if state["next_attack_team"] == "A" else "A",
        "opponents": [{**entry, "hp": enemy.health} for entry, enemy in zip(state["opponents"], enemies, strict=True)],
        "charge": min(MAX_CHARGE, (0 if use_skill else state["charge"]) + TURN_SECONDS * charge_per_second(player)),
        "carry": carry,
        "events": events[-60:],
    }
    return state, won, lost, before - dweller.health
