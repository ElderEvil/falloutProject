"""Schemas for interactive expedition sites (static definitions + API views)."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

RARITY_ORDER = ("common", "rare", "legendary")


def rarity_meets_floor(rarity: str, floor: str | None) -> bool:
    """Return whether a rolled rarity satisfies a minimum-rarity floor."""
    if floor is None:
        return True
    order = {name: index for index, name in enumerate(RARITY_ORDER)}
    return order.get(rarity.lower(), -1) >= order.get(floor.lower(), 0)


class EnemySpec(BaseModel):
    """Enemy reference: table lookup by name, or a full inline boss spec."""

    name: str
    difficulty: int | None = Field(default=None, ge=1, le=5)
    min_damage: int | None = Field(default=None, ge=0)
    max_damage: int | None = Field(default=None, ge=0)


class NodeBranch(BaseModel):
    """Terminal outcome of one option: cache, combat, trap, trade, or nothing."""

    cache_tier: Literal["small", "standard", "rich"] | None = None
    cache_item: Literal["junk", "weapon", "outfit"] | None = None
    cache_floor: str | None = None
    combat_enemies: list[EnemySpec] | None = None
    trap_damage_min: int | None = None
    trap_damage_max: int | None = None
    trade_cost_caps: int | None = None


class NodeOption(BaseModel):
    """One player-facing option on a choice/trap node."""

    id: str
    label: str
    stat: str
    difficulty: int = Field(ge=1, le=5)
    success: NodeBranch = Field(default_factory=NodeBranch)
    failure: NodeBranch = Field(default_factory=NodeBranch)


class SiteNode(BaseModel):
    """One room node: combat, choice, skill_check, trap, cache, or finale."""

    kind: Literal["combat", "choice", "skill_check", "trap", "cache", "finale"]
    prompt: str
    enemies: list[EnemySpec] = Field(default_factory=list)
    options: list[NodeOption] = Field(default_factory=list)
    stat: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    success: NodeBranch = Field(default_factory=NodeBranch)
    failure: NodeBranch = Field(default_factory=NodeBranch)
    damage_min: int | None = None
    damage_max: int | None = None
    radiation: int = 0
    cache_tier: Literal["small", "standard", "rich"] | None = None


class SiteRoom(BaseModel):
    """One room of an expedition site."""

    id: str
    name: str
    flavor: str
    node: SiteNode


class ItemRollSpec(BaseModel):
    """Elevated item roll: type, bounded rerolls toward a rarity floor."""

    type: Literal["weapon", "outfit", "junk"]
    floor: str | None = None
    rolls: int = Field(default=1, ge=1, le=5)


class RewardVault(BaseModel):
    """Finale payout: caps range, item roll, and guaranteed extras."""

    caps_min: int = Field(ge=0)
    caps_max: int = Field(ge=0)
    item: ItemRollSpec | None = None
    junk_bundles: int = Field(default=0, ge=0)
    stimpaks: int = Field(default=0, ge=0)


class SiteDefinition(BaseModel):
    """One hand-authored expedition site."""

    id: str
    name: str
    flavor: str
    min_dweller_level: int = Field(ge=1)
    rooms: list[SiteRoom] = Field(min_length=1)
    reward_vault: RewardVault


class ExpeditionSiteList(BaseModel):
    """Top-level shape of expedition_sites.json."""

    sites: list[SiteDefinition]


class NodeOptionView(BaseModel):
    """Player-facing option with precomputed success odds."""

    id: str
    label: str
    stat: str
    difficulty: int
    success_odds: float


class SiteNodeView(BaseModel):
    """Player-facing node prompt."""

    kind: str
    prompt: str
    options: list[NodeOptionView] = Field(default_factory=list)
    enemy_names: list[str] = Field(default_factory=list)


class CombatEntry(BaseModel):
    """One enemy engagement inside a room fight."""

    enemy: str
    victory: bool
    damage_taken: int = 0


class NodeOutcome(BaseModel):
    """What the last resolution did."""

    text: str
    damage_taken: int = 0
    caps_gained: int = 0
    loot_gained: list[str] = Field(default_factory=list)
    # Per-enemy engagements, in fight order, so the client can present a battle.
    combat: list[CombatEntry] = Field(default_factory=list)


class SiteRoomView(BaseModel):
    """Current room state returned by every expedition endpoint."""

    exploration_id: UUID
    site_id: str
    site_name: str
    room_index: int
    room_total: int
    room_name: str
    flavor: str
    node: SiteNodeView
    can_retreat: bool
    status: str
    outcome: NodeOutcome | None = None
    finale_paid: bool = False
    defeated: bool = False
    # Live dweller condition, so the client can show the stake of push-on vs retreat.
    dweller_health: int = 0
    dweller_max_health: int = 0


class AvailableSiteView(BaseModel):
    """One expedition site the dweller may currently enter."""

    id: str
    name: str
    flavor: str
    min_dweller_level: int
    room_total: int


class ExpeditionResolveRequest(BaseModel):
    """Resolve the current node; choice_id required for choice/trap-with-options nodes."""

    choice_id: str | None = None


class ExpeditionEnterRequest(BaseModel):
    """Enter an expedition site on an active exploration."""

    site_id: str
