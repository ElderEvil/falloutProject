"""Unit tests for expedition site definitions and loading."""

import pytest
from pydantic import ValidationError

from app.schemas.expedition import SiteDefinition
from app.services.exploration import data_loader


def test_sites_load_and_validate():
    sites = data_loader.load_expedition_sites()
    assert {site.id for site in sites} == {"red_rocket", "super_duper_mart"}
    for site in sites:
        assert isinstance(site, SiteDefinition)
        assert site.rooms
        assert site.rooms[-1].node.kind == "finale"


def test_red_rocket_shape():
    site = data_loader.get_expedition_site("red_rocket")
    assert site is not None
    assert site.min_dweller_level == 3
    assert [room.id for room in site.rooms] == ["forecourt", "garage", "bunker"]
    assert site.rooms[0].node.kind == "trap"
    assert site.rooms[1].node.kind == "combat"
    assert site.reward_vault.caps_min == 80


def test_super_duper_mart_shape():
    site = data_loader.get_expedition_site("super_duper_mart")
    assert site is not None
    assert site.min_dweller_level == 5
    boss = site.rooms[2].node.enemies[0]
    assert boss.name == "Raider Boss"
    assert boss.min_damage == 25
    assert site.reward_vault.item is not None
    assert site.reward_vault.item.floor == "rare"


def test_unknown_site_returns_none():
    assert data_loader.get_expedition_site("no_such_site") is None


def test_invalid_site_definition_rejected():
    with pytest.raises(ValidationError) as exc_info:
        SiteDefinition(
            id="bad",
            name="Bad",
            flavor="Bad",
            coord_x=50,
            coord_y=50,
            min_dweller_level=1,
            rooms=[],
            reward_vault={"caps_min": 0, "caps_max": 10},
        )
    assert any("rooms" in error["loc"] for error in exc_info.value.errors())
