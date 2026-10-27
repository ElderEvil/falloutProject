"""Schemas for interactive expedition sites (static definitions + API views)."""

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import ExpeditionSceneId
from app.schemas.arena import ArenaFighter
from app.schemas.combat import CombatAction

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
    arena_key: str | None = None
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


class TriviaOption(BaseModel):
    """One answer choice on a lore-trivia node."""

    id: str
    label: str


class TriviaQuestion(BaseModel):
    """A hand-authored lore question with its server-side answer key."""

    id: str
    prompt: str
    options: list[TriviaOption] = Field(min_length=2, max_length=4)
    correct_option_id: str

    @model_validator(mode="after")
    def correct_option_exists(self) -> Self:
        option_ids = [option.id for option in self.options]
        if len(set(option_ids)) != len(option_ids):
            raise ValueError(f"trivia question {self.id!r} has duplicate option ids")
        if self.correct_option_id not in option_ids:
            raise ValueError(f"trivia question {self.id!r} answer is not one of its options")
        return self


class TriviaRaider(BaseModel):
    """One raider persona who poses the trivia question."""

    id: str
    name: str
    gender: Literal["female", "male"]
    intro: str
    correct_line: str
    wrong_line: str
    image_url: str | None = None
    alt_image_url: str | None = None


class SiteNode(BaseModel):
    """One room node: combat, choice, trap, trivia, or finale."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["combat", "choice", "trap", "finale", "trivia"]
    prompt: str
    enemies: list[EnemySpec] = Field(default_factory=list)
    options: list[NodeOption] = Field(default_factory=list)
    trivia_questions: list[TriviaQuestion] = Field(default_factory=list)
    raiders: list[TriviaRaider] = Field(default_factory=list)
    stat: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    damage_min: int | None = None
    damage_max: int | None = None
    radiation: int = 0

    @model_validator(mode="after")
    def trivia_has_content(self) -> Self:
        if self.kind != "trivia":
            return self
        if not self.trivia_questions:
            raise ValueError("trivia node needs at least one question")
        question_ids = [question.id for question in self.trivia_questions]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("trivia node has duplicate question ids")
        if not self.raiders:
            raise ValueError("trivia node needs at least one raider")
        raider_ids = [raider.id for raider in self.raiders]
        raider_names = [raider.name for raider in self.raiders]
        if len(set(raider_ids)) != len(raider_ids) or len(set(raider_names)) != len(raider_names):
            raise ValueError("trivia node has duplicate raider ids or names")
        if not self.enemies:
            raise ValueError("trivia node needs enemies for wrong answers")
        return self


class SiteRoom(BaseModel):
    """One room of an expedition site."""

    id: str
    name: str
    flavor: str
    node: SiteNode


class ItemRollSpec(BaseModel):
    """One item with bounded reroll attempts toward a rarity floor."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["weapon", "outfit", "junk"]
    floor: str | None = None
    attempts: int = Field(default=1, ge=1, le=5)

    @model_validator(mode="after")
    def attempts_need_floor(self) -> Self:
        if self.floor is None and self.attempts != 1:
            raise ValueError("multiple attempts require a rarity floor")
        return self


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
    # World-map position on the same 0-100 grid as WorldLocation.coord_x/coord_y.
    coord_x: float = Field(ge=0, le=100)
    coord_y: float = Field(ge=0, le=100)
    min_dweller_level: int = Field(ge=1)
    rooms: list[SiteRoom] = Field(default_factory=list)
    # Original rooms remain readable for already-saved runs. New spatial visits
    # resolve this single encounter and award the site's haul in the same transaction.
    encounter: SiteRoom | None = None
    scene_id: ExpeditionSceneId | None = None
    lore: str = ""
    # Encounter-only tuning: shared arena catalog stats remain unchanged.
    enemy_power_scale: float = Field(default=0.12, gt=0, le=5)
    enemy_health_scale: float = Field(default=0.3, gt=0, le=5)
    reward_vault: RewardVault

    @model_validator(mode="after")
    def requires_playable_content(self) -> Self:
        if not self.rooms and self.encounter is None:
            raise ValueError("site needs rooms or an encounter")
        return self


class ExpeditionSiteList(BaseModel):
    """Top-level shape of expedition_sites.json."""

    sites: list[SiteDefinition]


class NodeOptionView(BaseModel):
    """Player-facing option; stat and odds are null for trivia answer choices."""

    id: str
    label: str
    stat: str | None = None
    difficulty: int | None = None
    success_odds: float | None = None


class SiteNodeView(BaseModel):
    """Player-facing node prompt."""

    kind: str
    prompt: str
    question: str | None = None
    raider_image_url: str | None = None
    raider_alt_image_url: str | None = None
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


class SiteCombatEvent(BaseModel):
    id: str
    message: str
    action: CombatAction | None = None


class SiteCombatView(BaseModel):
    round: int
    next_attack_team: Literal["A", "B"] = "A"
    fighters: list[ArenaFighter]
    events: list[SiteCombatEvent] = Field(default_factory=list)


class SiteRoomView(BaseModel):
    """Current room state returned by every expedition endpoint."""

    exploration_id: UUID
    site_id: str
    site_name: str
    room_index: int
    room_total: int
    room_name: str
    room_names: list[str] = Field(default_factory=list)
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
    scene_id: ExpeditionSceneId | None = None
    lore: str = ""
    combat_state: SiteCombatView | None = None


class AvailableSiteView(BaseModel):
    """One expedition site the dweller may currently enter."""

    id: str
    name: str
    flavor: str
    min_dweller_level: int
    room_total: int
    scene_id: ExpeditionSceneId | None = None
    enemy_names: list[str] = Field(default_factory=list)
    threat: Literal["low", "moderate", "high"] | None = None


class ExpeditionResolveRequest(BaseModel):
    """Resolve the current node; choice_id required for choice/trap-with-options nodes."""

    choice_id: str | None = None
    use_skill: bool = False
    expected_round: int | None = Field(default=None, ge=0)


class ExpeditionEnterRequest(BaseModel):
    """Enter an expedition site on an active exploration."""

    site_id: str
