"""Clearance Protocol contracts for existing place, bio and exploration paths."""

import json
from pathlib import Path
from string import Formatter

from app.options.bios import ZONE_RUMORS
from app.services.exploration.data_loader import load_event_templates
from app.utils.place_groups import get_place_group, group_for_place_name
from app.utils.place_seed import load_seed_entries

DATA_DIR = Path(__file__).parents[2] / "data"
PROTOCOL_PLACES = {
    "The Outlook Station": "observation_facility",
    "The Mile-Deep Shelter": "vertical_refuge",
    "The Heartworks": "power",
}


def test_protocol_places_have_explicit_curated_discovery_routes() -> None:
    seeds = {entry["name"]: entry for entry in load_seed_entries()}
    templates = json.loads((DATA_DIR / "dwellers" / "rare.json").read_text(encoding="utf-8"))
    visited = {place for template in templates for place in template.get("visited_places", [])}
    for name, group in PROTOCOL_PLACES.items():
        assert name in visited, f"{name} has no curated visited_places route"
        assert "visited" in seeds[name]["roles"]
        assert group_for_place_name(name) == group
        assert get_place_group(group) is not None
        assert any(name in template["bio"] and name in template["visited_places"] for template in templates)


def test_protocol_relics_are_present_in_readable_place_descriptions() -> None:
    descriptions = " ".join(
        entry["description"] for entry in load_seed_entries() if entry["name"] in PROTOCOL_PLACES
    ).casefold()
    for clue in (
        "exterior lens cloth",
        "clearance suit patch",
        "sealed cleaning kit",
        "optics checklist",
        "continuity compact",
        "thermal seal tape",
        "department-issue heat tape",
    ):
        assert clue in descriptions
    assert "voluntary" in descriptions
    assert "mandatory" in descriptions
    assert "printing error" in descriptions
    assert "training reel" in descriptions


def test_protocol_rest_flavor_keeps_the_existing_healing_contract() -> None:
    templates = load_event_templates()["rest"]
    for template in templates:
        placeholders = {field for _, field, _, _ in Formatter().parse(template) if field}
        assert placeholders == {"health"}
        assert "17" in template.format(health=17)
    assert any("Exterior Clearance Detail" in template for template in templates)
    assert any("Continuity Compact" in template for template in templates)
    assert any("Thermal Seal Tape" in template for template in templates)
    assert any("incompatible blue skies" in template for template in templates)


def test_protocol_rumors_keep_secondhand_contradictory_accounts() -> None:
    assert any("Department of Exterior Continuity" in line and "forgery" in line for line in ZONE_RUMORS)
    assert any("polishing cloth" in line and "his sister said" in line for line in ZONE_RUMORS)
    assert any("Heat Tape" in line and "supervisor says" in line for line in ZONE_RUMORS)
    assert any("Quiet Zone" in line for line in ZONE_RUMORS)
