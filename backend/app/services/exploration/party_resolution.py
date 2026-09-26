"""Deterministic party combat for dispatch arrivals (issue 772, phase 3).

A dispatch party fights as a unit: the members' combat power is aggregated with
no leader bonus and compared against the tier threat. The outcome is a pure
function of the inputs so tests and replays are deterministic.
"""

from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.utils.combat import total_combat_power


def resolve_party_combat(members: list[Dweller], difficulty: int) -> tuple[bool, int]:
    """Party victory and total damage from aggregate power versus tier threat."""
    cfg = game_config.exploration.dispatch
    party_power = total_combat_power(members)
    threat = difficulty * cfg.power_per_difficulty
    victory = party_power >= threat
    shortfall = max(0.0, (threat - party_power) / threat) if threat > 0 else 0.0
    total_damage = max(1, round(difficulty * cfg.damage_per_difficulty * (1 + shortfall)))
    return victory, total_damage


def distribute_damage(total_damage: int, party_size: int) -> list[int]:
    """Split damage across the party; the anchor absorbs any remainder."""
    size = max(1, party_size)
    per_member = max(1, total_damage // size)
    shares = [per_member] * size
    shares[0] = max(0, shares[0] + (total_damage - per_member * size))
    return shares


def apply_party_haul_loss(exploration: Exploration, party_size: int, deaths: int) -> None:
    """Trim the single shared haul by the dead members' carried portion.

    The haul itself is never split; the loss is proportional to the dead share
    of the party, so a wipe removes everything and a lone survivor keeps a
    proportional remainder.
    """
    if deaths <= 0 or party_size <= 0:
        return
    survivors = party_size - deaths
    if survivors <= 0:
        exploration.total_caps_found = 0
        exploration.loot_collected = []
        return
    exploration.total_caps_found -= exploration.total_caps_found * deaths // party_size
    keep = len(exploration.loot_collected) * survivors // party_size
    exploration.loot_collected = exploration.loot_collected[:keep]
