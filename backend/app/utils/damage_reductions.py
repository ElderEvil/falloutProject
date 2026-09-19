"""Pure damage-reduction resolver: one place that answers what a dweller resists per channel.

Every combat/radiation reduction source feeds this module, and every application
point calls it once. Shares combine multiplicatively (``1 - product(1 - r)``) so
the result is order-independent, and the amount is truncated exactly once, at the
end. Pure and session-free: it reads identity modifiers and the equipped outfit,
never the database.
"""

from dataclasses import dataclass
from functools import reduce
from operator import mul
from typing import TYPE_CHECKING, cast

from app.core.enums import DamageChannel
from app.options.identity_modifiers import identity_modifiers_for
from app.utils.equipped import equipped_outfit
from app.utils.hazard_resist import outfit_fire_resist, outfit_radiation_resist

if TYPE_CHECKING:
    from app.models.outfit import Outfit


@dataclass(frozen=True)
class DamageReductions:
    """The reduction shares a dweller contributes on one channel, combined once."""

    shares: tuple[float, ...] = ()
    immune: bool = False

    @property
    def combined_share(self) -> float:
        """Multiplicative-complement combination: 1 - product(1 - r). Order-independent."""
        return 1.0 - reduce(mul, (1.0 - share for share in self.shares), 1.0)

    def apply(self, amount: int) -> int:
        """The amount after reductions — one truncation, at the end. Immune means zero."""
        if self.immune:
            return 0
        return int(amount * (1.0 - self.combined_share))


def damage_reductions(
    dweller: object,
    channel: DamageChannel,
    *,
    team_share: float = 0.0,
    resisted_by_outfit: bool = True,
) -> DamageReductions:
    """The reduction shares a dweller contributes on a channel.

    PHYSICAL → identity ``incident_response_pct``.
    FIRE → identity ``incident_response_pct`` + ``outfit_fire_resist``.
    RADIATION → identity ``radiation_resist_pct`` (+ immunity from ``radiation_immune``)
    + ``outfit_radiation_resist`` when ``resisted_by_outfit``.
    ``team_share`` is added for every channel when > 0.
    """
    modifiers = identity_modifiers_for(dweller)
    shares: list[float] = []
    immune = False
    if channel is DamageChannel.PHYSICAL:
        if modifiers.incident_response_pct:
            shares.append(modifiers.incident_response_pct)
    elif channel is DamageChannel.FIRE:
        if modifiers.incident_response_pct:
            shares.append(modifiers.incident_response_pct)
        fire_resist = outfit_fire_resist(cast("Outfit | None", equipped_outfit(dweller)))
        if fire_resist:
            shares.append(fire_resist)
    elif channel is DamageChannel.RADIATION:
        immune = modifiers.radiation_immune
        if modifiers.radiation_resist_pct:
            shares.append(modifiers.radiation_resist_pct)
        if resisted_by_outfit:
            rad_resist = outfit_radiation_resist(cast("Outfit | None", equipped_outfit(dweller)))
            if rad_resist:
                shares.append(rad_resist)
    if team_share > 0:
        shares.append(team_share)
    return DamageReductions(shares=tuple(shares), immune=immune)
