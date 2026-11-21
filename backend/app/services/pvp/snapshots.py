"""Builds frozen duel snapshots from live dwellers.

This is the only module allowed to call combat_power: it reads live ORM rows and
game_config, then stores plain numbers so a later replay cannot drift when stats,
equipment or balance change.
"""

from typing import Any
from uuid import UUID

from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.utils.combat import combat_power

# Frozen into every snapshot; changing these only affects future duels.
TUNING: dict[str, float | int] = {
    "max_rounds": 10,
    "hp_per_power": 2.0,
    "level_bonus_damage": 0.5,
}

POWER_BANDS: tuple[tuple[float, str], ...] = ((500.0, "elite"), (250.0, "strong"), (100.0, "steady"))


def power_band(total_power: float) -> str:
    """Coarse band shown on the board; exact power stays server-side."""
    for floor, band in POWER_BANDS:
        if total_power >= floor:
            return band
    return "light"


def build_snapshot(vault: Vault, dwellers: list[Dweller], tuning: dict[str, float] | None = None) -> dict[str, Any]:
    """Freeze a party's per-dweller power, damage range, level bonus and the tuning used.

    ``tuning`` lets the accepting side adopt the challenger's frozen block, so a deploy
    between post and accept cannot make a duel unsettleable.
    """
    members = []
    for dweller in dwellers:
        power = combat_power(dweller)
        members.append(
            {
                "dweller_id": str(dweller.id),
                "name": dweller.display_name,
                "power": round(power, 3),
                "damage_min": round(power * 0.35),
                "damage_max": round(power * 0.65),
                "level_bonus": dweller.level * game_config.combat.level_bonus_multiplier,
            }
        )
    return {
        "vault_id": str(vault.id),
        "vault_name": str(vault),
        "party_size": len(members),
        "power_band": power_band(sum(float(member["power"]) for member in members)),
        "members": members,
        "tuning": dict(tuning if tuning is not None else TUNING),
    }


PARTY_LIMIT = 3


def select_party(dwellers: list[Dweller], dweller_ids: list[UUID]) -> list[Dweller]:
    """The requested dwellers in request order — the same roster an expedition dispatch takes.

    No implicit default: the server never decides who fights on the player's behalf, exactly as
    dispatch requires an explicit party.
    """
    if not dweller_ids:
        raise ValueError("Pick at least one dweller to fight.")
    if len(dweller_ids) > PARTY_LIMIT:
        raise ValueError(f"A party is at most {PARTY_LIMIT} dwellers.")
    if len(set(dweller_ids)) != len(dweller_ids):
        raise ValueError("Each dweller may only fight once.")
    by_id = {dweller.id: dweller for dweller in dwellers}
    missing = [str(dweller_id) for dweller_id in dweller_ids if dweller_id not in by_id]
    if missing:
        raise ValueError(f"Unknown dwellers: {', '.join(missing)}")
    return [by_id[dweller_id] for dweller_id in dweller_ids]
