"""Unit tests for expedition site definitions and loading."""

import pytest
from pydantic import ValidationError

from app.schemas.expedition import SiteDefinition
from app.services import catalog_service as data_loader


def test_sites_load_and_validate():
    sites = data_loader.load_expedition_sites()
    assert {site.id for site in sites} == {
        "red_rocket",
        "super_duper_mart",
        "abandoned_campsite",
        "roadside_supply_truck",
        "forgotten_shack",
        "collapsed_subway",
        "rusted_midway",
        "frozen_research_outpost",
        "raider_tollbooth",
        "vault_68",
        "vault_69",
    }
    for site in sites:
        assert isinstance(site, SiteDefinition)
        assert site.rooms or site.encounter
        assert site.encounter is not None
        assert site.encounter.node.kind in {"combat", "choice", "trivia"}
        assert site.lore
        if site.scenario_only:
            assert not site.rooms
            assert site.encounter.node.kind == "choice"
        if len(site.rooms) > 1:
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


def test_raider_tollbooth_shape():
    site = data_loader.get_expedition_site("raider_tollbooth")
    assert site is not None
    assert site.encounter is not None
    node = site.encounter.node
    assert node.kind == "trivia"
    assert [enemy.arena_key for enemy in node.enemies] == ["raider"]
    assert len(node.trivia_questions) >= 5
    for question in node.trivia_questions:
        assert question.correct_option_id in {option.id for option in question.options}
    assert {raider.gender for raider in node.raiders} == {"female", "male"}
    assert len({raider.name for raider in node.raiders}) == len(node.raiders)
    assert all(raider.intro and raider.correct_line and raider.wrong_line for raider in node.raiders)
    assert all(raider.image_url and raider.alt_image_url for raider in node.raiders)
    assert site.reward_vault.caps_min == 40


def test_raider_variant_assets_are_shipped_and_transparent():
    from pathlib import Path

    from PIL import Image

    static = Path(__file__).resolve().parents[2] / "static"
    site = data_loader.get_expedition_site("raider_tollbooth")
    assert site is not None
    assert site.encounter is not None
    for raider in site.encounter.node.raiders:
        for url in (raider.image_url, raider.alt_image_url):
            assert url is not None
            assert url.startswith("/static/raider_images/")
            assert "?v=" in url
            path = static / url.split("?", 1)[0].removeprefix("/static/")
            assert path.exists(), url
            with Image.open(path) as image:
                assert image.mode == "RGBA"
                assert image.height == 902
    assert not (static / "raider_images/base").exists()
    assert not (static / "creature_images/assembled/raider.webp").exists()


def test_trivia_question_rejects_unknown_answer():
    from app.schemas.expedition import TriviaOption, TriviaQuestion

    with pytest.raises(ValidationError, match="answer is not one of its options"):
        TriviaQuestion(
            id="q",
            prompt="?",
            options=[TriviaOption(id="a", label="A"), TriviaOption(id="b", label="B")],
            correct_option_id="c",
        )


def test_trivia_encounter_needs_questions():
    from app.services.catalog_service import validate_site_content
    from app.utils.exceptions import ValidationException

    site = data_loader.get_expedition_site("raider_tollbooth").model_copy(deep=True)
    site.encounter.node.trivia_questions = []
    with pytest.raises(ValidationException, match="needs trivia questions and raiders"):
        validate_site_content(site)


def test_trivia_encounter_needs_raiders():
    from app.services.catalog_service import validate_site_content
    from app.utils.exceptions import ValidationException

    site = data_loader.get_expedition_site("raider_tollbooth").model_copy(deep=True)
    site.encounter.node.raiders = []
    with pytest.raises(ValidationException, match="needs trivia questions and raiders"):
        validate_site_content(site)


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
    assert "rooms or an encounter" in str(exc_info.value)


@pytest.mark.parametrize(
    "site",
    [site for site in data_loader.load_expedition_sites() if not site.scenario_only],
    ids=lambda site: site.id,
)
def test_scene_rosters_and_intro_balance(site):
    from app.models.dweller import Dweller
    from app.services.exploration.site_combat_service import initial_combat, resolve_turn
    from app.tests.factory.dwellers import create_rush_dweller_payload

    # A modest unarmed dweller is a deliberately conservative first-release baseline.
    dweller = Dweller(**create_rush_dweller_payload(strength=3), level=site.min_dweller_level, radiation=0)
    state = initial_combat(site)
    won = lost = False
    for _ in range(160):
        state, won, lost, _ = resolve_turn(state, dweller, use_skill=False)
        if won or lost:
            break
    assert won
    assert not lost
    assert dweller.health >= 60


def test_desert_wildlife_rejected_in_arctic_scene():
    from app.services.catalog_service import validate_site_content
    from app.utils.exceptions import ValidationException

    desert = data_loader.get_expedition_site("roadside_supply_truck")
    with pytest.raises(ValidationException, match="does not belong"):
        validate_site_content(desert.model_copy(update={"scene_id": "arctic_research_station"}))


@pytest.mark.parametrize("problem", ["missing_scene", "choice_encounter", "empty_roster", "wrong_pool"])
def test_encounter_authoring_errors_are_rejected_at_validation(problem):
    from app.services.catalog_service import validate_site_content
    from app.utils.exceptions import ValidationException

    site = data_loader.get_expedition_site("roadside_supply_truck").model_copy(deep=True)
    if problem == "missing_scene":
        site.scene_id = None
    elif problem == "choice_encounter":
        site.encounter.node.kind = "choice"
    elif problem == "empty_roster":
        site.encounter.node.enemies = []
    else:
        site.scene_id = "arctic_research_station"
    with pytest.raises(ValidationException):
        validate_site_content(site)


def test_catalog_rejects_invalid_encounter_before_returning_sites(tmp_path, monkeypatch):
    import json

    from app.utils.exceptions import ValidationException

    site = data_loader.get_expedition_site("roadside_supply_truck").model_dump(mode="json")
    site["scene_id"] = "arctic_research_station"
    (tmp_path / "expedition_sites.json").write_text(json.dumps({"sites": [site]}))
    with monkeypatch.context() as patch:
        patch.setattr(data_loader, "EXPLORATION_DIR", tmp_path)
        data_loader.load_expedition_sites.cache_clear()
        try:
            with pytest.raises(ValidationException, match="does not belong"):
                data_loader.load_expedition_sites()
        finally:
            data_loader.load_expedition_sites.cache_clear()
