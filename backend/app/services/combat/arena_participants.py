"""Arena participant model and fighters — the shared combat-view vocabulary.

A participant is one seat in a match: a dweller, a catalog creature opponent,
or a training bot. Construction, HP persistence back into ``ArenaState`` JSON,
skill-charge velocity, and the API fighter mapping all live here so the
orchestrating service keeps pure flow.
"""

from dataclasses import dataclass

from pydantic import UUID4

from app.models.arena_state import ArenaState
from app.models.dweller import Dweller
from app.options.identity_modifiers import effective_stat
from app.schemas.arena import ArenaActiveSkill, ArenaFighter
from app.services.catalog_service import list_arena_creatures
from app.services.combat.weapon_skill_service import MAX_CHARGE, weapon_skill
from app.utils.combat import combat_power

BASE_CHARGE_PER_SECOND = 2.0
PERCEPTION_CHARGE_FACTOR = 0.4


@dataclass
class ArenaParticipant:
    key: str
    name: str
    short_name: str
    power: float
    health: int
    max_health: int
    is_creature: bool = False
    is_robot: bool = False
    dweller: Dweller | None = None


def participant_from_dweller(dweller: Dweller) -> ArenaParticipant:
    return ArenaParticipant(
        key=str(dweller.id),
        name=dweller.display_name,
        short_name=dweller.first_name,
        power=combat_power(dweller),
        health=dweller.health,
        max_health=dweller.effective_max_health,
        dweller=dweller,
    )


def dweller_participants(slots: list[UUID4 | None], by_id: dict[str, Dweller]) -> list[ArenaParticipant]:
    """Participants for the filled slots; empty when any slot's dweller is gone."""
    participants = []
    for slot in slots:
        if slot is None:
            continue
        member = by_id.get(str(slot))
        if member is None:
            return []
        participants.append(participant_from_dweller(member))
    return participants


def catalog_participants(entries: list[dict], side: str = "") -> list[ArenaParticipant]:
    """Creature opponents or training bots from persisted catalog entries."""
    robots = {entry["key"] for entry in list_arena_creatures() if entry.get("is_robot")}
    return [
        ArenaParticipant(
            key=f"{entry['key']}#{side}{index}",
            name=entry["name"],
            short_name=entry["name"],
            power=float(entry["power"]),
            health=int(entry["hp"]),
            max_health=int(entry["max_hp"]),
            is_creature=True,
            is_robot=bool(entry.get("is_robot", entry["key"] in robots)),
        )
        for index, entry in enumerate(entries)
    ]


def persist_creature_hp(state: ArenaState, team_a: list[ArenaParticipant], team_b: list[ArenaParticipant]) -> None:
    """Persist both opponent and support HP without mutating JSON in place."""
    by_id = {member.key: member.health for member in (*team_a, *team_b)}
    if state.opponents:
        state.opponents = [
            {**entry, "hp": by_id.get(f"{entry['key']}#{index}", entry["hp"])}
            for index, entry in enumerate(state.opponents)
        ]
    if state.support_bots:
        state.support_bots = {
            side: {**entry, "hp": by_id.get(f"{entry['key']}#{side}0", entry["hp"])}
            for side, entry in state.support_bots.items()
        }


def charge_per_second(participant: ArenaParticipant) -> float:
    """Skill-charge velocity: slower creatures charge at the base rate only."""
    if participant.dweller is None:
        return BASE_CHARGE_PER_SECOND
    return BASE_CHARGE_PER_SECOND + effective_stat(participant.dweller, "perception") * PERCEPTION_CHARGE_FACTOR


def participant_out(participant: ArenaParticipant, state: ArenaState) -> ArenaFighter:
    """Map a participant onto the API ``ArenaFighter`` shape for the arena view."""
    skill = weapon_skill(participant.dweller) if participant.dweller else None
    return ArenaFighter(
        active_skill=(
            ArenaActiveSkill(
                name=skill.name,
                icon=skill.icon,
                description=skill.description,
                charge=int(min(MAX_CHARGE, (state.skill_charge or {}).get(participant.key, 0))),
                queued=participant.key in (state.queued_skill_ids or []),
            )
            if skill
            else None
        ),
        id=participant.key,
        name=participant.name,
        level=participant.dweller.level if participant.dweller else 0,
        health=participant.health,
        max_health=participant.max_health,
        power=participant.power,
        is_creature=participant.is_creature,
        is_robot=participant.is_robot,
        image_url=participant.dweller.image_url if participant.dweller else None,
        thumbnail_url=participant.dweller.thumbnail_url if participant.dweller else None,
        age_group=(
            participant.dweller.age_group.value if participant.dweller and participant.dweller.age_group else None
        ),
        race=((participant.dweller.visual_attributes or {}).get("race") if participant.dweller else None),
    )
