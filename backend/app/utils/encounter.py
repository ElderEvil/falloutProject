"""Deterministic danger bands for map clearance (no RNG)."""

from dataclasses import dataclass

from app.core.enums import EncounterBand
from app.core.game_config import game_config

BASELINE_SPECIAL = 5


@dataclass(frozen=True)
class EncounterProfile:
    danger: int
    min_party: int
    ref_level: int
    required_power: float
    complete_power: float

    def band(self, party_power: float) -> EncounterBand:
        if party_power >= self.complete_power:
            return EncounterBand.CLEAN
        if party_power >= self.required_power:
            return EncounterBand.COSTLY
        return EncounterBand.REPELLED


def reference_power(level: int) -> float:
    """Power of one base-SPECIAL, unarmed dweller at ``level``."""
    weights = game_config.combat.weapon_stat_weights.get("unarmed") or {}
    stat_power = sum(BASELINE_SPECIAL * weight for weight in weights.values())
    return stat_power + level * game_config.combat.level_bonus_multiplier


def profile_for(difficulty: int) -> EncounterProfile:
    dispatch = game_config.exploration.dispatch
    danger = min(5, max(1, difficulty))
    row = dispatch.danger_profiles[danger]
    budget = row.min_party * reference_power(row.ref_level)
    return EncounterProfile(
        danger=danger,
        min_party=row.min_party,
        ref_level=row.ref_level,
        required_power=budget,
        complete_power=budget * dispatch.complete_mult,
    )


def band_damage(max_health: int, band: EncounterBand) -> int:
    """Damage one member takes for a band, as a rounded share of its own max HP."""
    pct = game_config.exploration.dispatch.band_damage_pct[band.value]
    return max(1, round(max_health * pct)) if pct > 0 else 0
