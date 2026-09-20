"""Data loader for exploration system."""

import json
from functools import lru_cache
from pathlib import Path

from app.schemas.expedition import ExpeditionSiteList, SiteDefinition
from app.schemas.exploration_event import EnemySchema

# Data directory paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
EXPLORATION_DIR = DATA_DIR / "exploration"
ITEMS_DIR = DATA_DIR / "items"


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


@lru_cache(maxsize=1)
def load_expedition_sites() -> list[SiteDefinition]:
    """Load hand-authored expedition site definitions from JSON (validated)."""
    sites_file = EXPLORATION_DIR / "expedition_sites.json"
    if not sites_file.exists():
        return []
    with sites_file.open() as f:
        return ExpeditionSiteList(**json.load(f)).sites


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
