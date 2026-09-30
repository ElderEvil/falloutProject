"""Arena actor reference resolution (issue #818).

The actor reference is derived from structured dweller fields (age group) plus
equipped items (outfit/weapon names) — never from portrait URLs or
``visual_attributes`` free text. Equipment changes therefore never regenerate
portraits: the actor is a manifest-driven layer stack, and portraits are only
rewritten by ``generate_photo`` (explicit, ``force=True`` required).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.enums import AssetRole
from app.utils.asset_manifest import ActorLayerSpec, resolve_record

if TYPE_CHECKING:
    from app.models.dweller import Dweller
    from app.schemas.arena import ArenaActor

#: Manifest catalog keys for the single adult base asset and the two prototype
#: equipment layers (issue #817 asset manifest).
ADULT_BASE_CATALOG_KEY = "adult.vault_suit"
OUTFIT_CATALOG_KEY = "overcoat"
WEAPON_CATALOG_KEY = "rifle"


@dataclass(frozen=True)
class ActorAssets:
    """Manifest-driven layer stack for one arena actor.

    ``variant_key`` is kept for the two-variant prototype but is ``None`` for
    now: there is a single base asset, and no variant assets are fabricated.
    """

    base_key: str
    variant_key: str | None
    canvas_width: int
    canvas_height: int
    baseline_y: int
    layers: tuple[ActorLayerSpec, ...]

    def to_arena_actor(self) -> ArenaActor:
        """Convert to the wire schema (lazy import keeps utils free of schema deps)."""
        from app.schemas.arena import ArenaActor, ArenaActorLayer

        return ArenaActor(
            base_key=self.base_key,
            variant_url=self.variant_key,
            canvas_width=self.canvas_width,
            canvas_height=self.canvas_height,
            baseline_y=self.baseline_y,
            layers=[
                ArenaActorLayer(
                    slot=layer.slot,
                    url=layer.path,
                    z=layer.z,
                    anchor_x=layer.anchor_x,
                    anchor_y=layer.anchor_y,
                    width=layer.width,
                    height=layer.height,
                )
                for layer in self.layers
            ],
        )


def get_actor_assets(
    dweller: Dweller,
    *,
    outfit_name: str | None,
    weapon_name: str | None,
) -> ActorAssets | None:
    """Resolve the manifest-driven actor layer stack for a dweller.

    Returns ``None`` for non-adult dwellers (the documented fallback to the
    portrait) or when no usable manifest record exists. Every layer path comes
    from the manifest — never hardcoded in Python.
    """
    if not dweller.is_mature:
        return None

    base = resolve_record(AssetRole.ARENA_ACTOR, ADULT_BASE_CATALOG_KEY)
    if base is None or base.actor is None:
        return None

    layers = list(base.actor.layers)

    # Prototype stand-in: any equipped outfit maps to the single overcoat layer
    # until per-outfit actor assets exist (issue #818 two-variant prototype).
    if outfit_name:
        outfit = resolve_record(AssetRole.ARENA_EQUIPMENT, OUTFIT_CATALOG_KEY)
        if outfit is not None and outfit.actor is not None:
            layers.extend(outfit.actor.layers)

    # Prototype stand-in: any equipped weapon maps to the single rifle layer.
    if weapon_name:
        weapon = resolve_record(AssetRole.ARENA_EQUIPMENT, WEAPON_CATALOG_KEY)
        if weapon is not None and weapon.actor is not None:
            layers.extend(weapon.actor.layers)

    return ActorAssets(
        base_key=base.catalog_key,
        variant_key=None,
        canvas_width=base.actor.canvas_width,
        canvas_height=base.actor.canvas_height,
        baseline_y=base.actor.baseline_y,
        layers=tuple(layers),
    )
