"""Static catalog loading shared by workshops, exploration, rewards, and seeding.

Owned outside the exploration package: weapons, outfits, junk, themes, and
discovery pools are cross-domain catalogs, not exploration internals.
"""

import json
from functools import lru_cache
from operator import itemgetter
from pathlib import Path

from app.core.enums import SPECIAL_STATS, ExpeditionSceneId
from app.schemas.expedition import EnemySpec, ExpeditionSiteList, SiteDefinition, TriviaRaider
from app.schemas.exploration_event import EnemySchema
from app.services.combat import incident_math
from app.utils.exceptions import ValidationException

# Data directory paths
DATA_DIR = Path(__file__).parent.parent / "data"
EXPLORATION_DIR = DATA_DIR / "exploration"
ITEMS_DIR = DATA_DIR / "items"
VAULT_DIR = DATA_DIR / "vault"
SITE_ENEMY_POOLS: dict[ExpeditionSceneId, frozenset[str]] = {
    ExpeditionSceneId.DESERT_HIGHWAY: frozenset(
        {"giant-radscorpion", "night-stalker", "raider", "super-mutant", "mole-rat-pack", "bloatfly"}
    ),
    ExpeditionSceneId.SUPERMARKET_INTERIOR: frozenset({"raider", "feral-ghoul", "radroach-swarm"}),
    ExpeditionSceneId.SUBWAY_STATION: frozenset({"feral-ghoul", "radroach-swarm", "mole-rat-pack"}),
    ExpeditionSceneId.AMUSEMENT_PARK: frozenset({"raider", "feral-ghoul", "radroach-swarm", "mole-rat-pack"}),
    ExpeditionSceneId.ARCTIC_RESEARCH_STATION: frozenset({"raider", "feral-ghoul"}),
}


@lru_cache(maxsize=1)
def load_enemies() -> list[dict]:
    """Load enemy definitions from JSON."""
    enemies_file = EXPLORATION_DIR / "enemies.json"
    if not enemies_file.exists():
        return _get_fallback_enemies()

    with enemies_file.open() as f:
        enemies_data = json.load(f)
        # Validate with Pydantic
        return [EnemySchema(**enemy).model_dump() for enemy in enemies_data]


def _creature_key(name: str) -> str:
    return name.strip().lower().replace(".", "").replace(" ", "-")


@lru_cache(maxsize=1)
def list_arena_creatures() -> list[dict]:
    """Reuse exploration scaling for arena wildlife and training robots, excluding raiders.

    Power reuses incident threat scaling; an incident threat of difficulty N is
    defeated by dealing ``raider_power(N)`` total damage, so that is its effective HP.
    """
    enemies = [enemy for enemy in load_enemies() if _creature_key(enemy["name"]) != "raider-gang"]
    enemies.extend(
        {"name": name, "difficulty": difficulty}
        for name, difficulty in (
            ("Bloatfly", 1),
            ("Radstag", 2),
            ("Night Stalker", 3),
            ("Mirelurk", 4),
            ("Yao Guai", 4),
        )
    )
    creatures: list[dict] = []
    for enemy in sorted(enemies, key=itemgetter("difficulty")):
        power = incident_math.raider_power(enemy["difficulty"])
        creatures.append(
            {
                "key": _creature_key(enemy["name"]),
                "name": enemy["name"],
                "power": power,
                "max_hp": int(power),
                "is_robot": False,
            }
        )
    for name, power, hp in (
        ("Training Eyebot", 30, 20),
        ("Training Mr. Handy", 20, 30),
        ("Training Protectron", 10, 60),
    ):
        creatures.append({"key": _creature_key(name), "name": name, "power": power, "max_hp": hp, "is_robot": True})
    return creatures


@lru_cache(maxsize=1)
def list_site_enemies() -> list[dict]:
    """Shared arena wildlife plus humanoids; no arena training robots in the wasteland."""
    enemies = [entry for entry in list_arena_creatures() if not entry.get("is_robot")]
    for key, name, difficulty in (
        ("raider", "Raider", 2),
        ("feral-ghoul", "Feral Ghoul", 2),
        ("super-mutant", "Super Mutant", 4),
    ):
        power = incident_math.raider_power(difficulty)
        enemies.append({"key": key, "name": name, "power": power, "max_hp": int(power), "is_robot": False})
    return enemies


def resolve_enemy_spec(spec: EnemySpec) -> EnemySchema:
    """Build an enemy from an inline boss spec or the shared enemy table."""
    if spec.min_damage is not None and spec.max_damage is not None:
        return EnemySchema(
            name=spec.name,
            difficulty=spec.difficulty or 1,
            min_damage=spec.min_damage,
            max_damage=spec.max_damage,
        )
    table = {enemy["name"].lower(): enemy for enemy in load_enemies()}
    entry = table.get(spec.name.lower())
    if entry is None:
        raise ValidationException(f"Unknown expedition enemy: {spec.name!r}")
    return EnemySchema(**entry)


def _require_floor_eligible(site: SiteDefinition, item_type: str, floor: str) -> None:
    """Reject site content whose reward floor has no catalog item at or above it (authoring error)."""
    from app.services.exploration.loot_calculator import loot_calculator

    if not loot_calculator.has_eligible(item_type, floor):
        raise ValidationException(f"Site {site.id}: no {item_type} at or above rarity {floor!r} in the catalog")


def validate_site_content(site: SiteDefinition) -> None:
    """Fail fast on authoring errors (bad stats, bad enemies, unsatisfiable floors) when loading the catalog."""
    if site.encounter is not None:
        if site.scene_id is None:
            raise ValidationException(f"Missing encounter scene in site {site.id}")
        node = site.encounter.node
        if site.scenario_only and node.kind == "choice":
            if not node.options:
                raise ValidationException(f"Scenario site {site.id} needs choice options")
        elif node.kind not in {"combat", "trivia"} or not node.enemies:
            raise ValidationException(f"Site {site.id} needs a combat or trivia encounter with enemies")
        if node.kind == "trivia" and not node.trivia_questions:
            raise ValidationException(f"Site {site.id} needs trivia questions")
        for spec in node.enemies:
            if spec.arena_key not in SITE_ENEMY_POOLS[site.scene_id]:
                raise ValidationException(f"Enemy {spec.arena_key!r} does not belong in scene {site.scene_id!r}")
    for room in [*site.rooms, *([site.encounter] if site.encounter is not None else [])]:
        node = room.node
        for stat in [option.stat for option in node.options] + ([node.stat] if node.stat else []):
            if stat not in SPECIAL_STATS:
                raise ValidationException(f"Unknown stat {stat!r} in site {site.id}")
        for spec in node.enemies:
            if spec.arena_key is not None:
                if not any(enemy["key"] == spec.arena_key for enemy in list_site_enemies()):
                    raise ValidationException(f"Unknown scene enemy {spec.arena_key!r}")
            else:
                resolve_enemy_spec(spec)
        for branch in (branch for option in node.options for branch in (option.success, option.failure)):
            for spec in branch.combat_enemies or []:
                resolve_enemy_spec(spec)
            if branch.cache_item is not None and branch.cache_floor is not None:
                _require_floor_eligible(site, branch.cache_item, branch.cache_floor)
    vault = site.reward_vault
    if vault.item is not None and vault.item.floor is not None:
        _require_floor_eligible(site, vault.item.type, vault.item.floor)


@lru_cache(maxsize=1)
def load_event_templates() -> dict:
    """Load event description templates from JSON."""
    templates_file = EXPLORATION_DIR / "event_templates.json"
    if not templates_file.exists():
        return _get_fallback_templates()

    with templates_file.open() as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_junk_items() -> list[dict]:
    """Load junk items from JSON."""
    junk_file = ITEMS_DIR / "junk.json"
    if not junk_file.exists():
        return []

    with junk_file.open() as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_weapons() -> list[dict]:
    """Load weapons from JSON."""
    weapons_file = ITEMS_DIR / "weapons.json"
    if not weapons_file.exists():
        return []

    with weapons_file.open() as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_outfits() -> list[dict]:
    """Load outfits from all outfit JSON files."""
    outfits_dir = ITEMS_DIR / "outfits"
    if not outfits_dir.exists():
        return []

    outfits = []
    for outfit_file in outfits_dir.glob("*.json"):
        with outfit_file.open() as f:
            outfits.extend(json.load(f))

    return outfits


@lru_cache(maxsize=1)
def load_pets() -> list[dict]:
    """Load the pet carrier pool (name + rarity)."""
    pets_file = ITEMS_DIR / "pets.json"
    if not pets_file.exists():
        return []

    with pets_file.open() as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_themes() -> list[dict]:
    """Load the Theme workshop's room-theme recipes."""
    themes_file = VAULT_DIR / "themes.json"
    if not themes_file.exists():
        return []

    with themes_file.open() as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_discovery_names() -> dict[str, list[str]]:
    """Load discovery location name pools from JSON."""
    names_file = EXPLORATION_DIR / "discovery_names.json"
    if not names_file.exists():
        return _get_fallback_discovery_names()

    with names_file.open() as f:
        return json.load(f)


def _get_fallback_discovery_names() -> dict[str, list[str]]:
    """Return fallback discovery name pools if JSON file is missing."""
    return {"prefixes": ["Old", "Abandoned", "Ruined"], "suffixes": ["Shack", "Depot", "Bunker"]}


def _read_expedition_document() -> ExpeditionSiteList:
    """Read and validate the expedition catalog document."""
    sites_file = EXPLORATION_DIR / "expedition_sites.json"
    if not sites_file.exists():
        return ExpeditionSiteList(sites=[])
    with sites_file.open() as f:
        document = ExpeditionSiteList(**json.load(f))
    if (
        any(site.encounter is not None and site.encounter.node.kind == "trivia" for site in document.sites)
        and not document.trivia_raiders
    ):
        raise ValidationException("Trivia sites need a shared raider roster")
    return document


@lru_cache(maxsize=1)
def load_expedition_sites() -> list[SiteDefinition]:
    """Load hand-authored expedition site definitions from JSON (validated)."""
    sites = _read_expedition_document().sites
    for site in sites:
        validate_site_content(site)
    return sites


@lru_cache(maxsize=1)
def load_trivia_raiders() -> list[TriviaRaider]:
    """Return the shared raider personas used by trivia encounters."""
    return list(_read_expedition_document().trivia_raiders)


def get_expedition_site(site_id: str) -> SiteDefinition | None:
    """Return one site definition by id, or None when unknown."""
    return next((site for site in load_expedition_sites() if site.id == site_id), None)


def _get_fallback_enemies() -> list[dict]:
    """Return fallback enemy data if JSON file is missing."""
    return [
        {"name": "Radroach swarm", "difficulty": 1, "min_damage": 5, "max_damage": 15},
        {"name": "Mole Rat pack", "difficulty": 2, "min_damage": 10, "max_damage": 20},
        {"name": "Raider gang", "difficulty": 3, "min_damage": 15, "max_damage": 30},
        {"name": "Giant Radscorpion", "difficulty": 4, "min_damage": 20, "max_damage": 40},
        {"name": "Deathclaw", "difficulty": 5, "min_damage": 30, "max_damage": 50},
    ]


def _get_fallback_templates() -> dict:
    """Return fallback event templates if JSON file is missing."""
    return {
        "combat": {
            "victory": ["Defeated {enemy}! Took {damage} damage."],
            "defeat": ["Barely survived {enemy}. Took {damage} damage."],
        },
        "loot": ["Found {item} and {caps} caps!"],
        "danger": ["Took {damage} damage from wasteland hazard."],
        "rest": ["Rested and recovered {health} HP."],
    }
