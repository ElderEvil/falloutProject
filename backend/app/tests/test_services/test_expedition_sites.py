import json
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from app.models.dweller import Dweller
from app.schemas.expedition import ExpeditionSiteList, SiteDefinition, TriviaOption, TriviaQuestion
from app.services import catalog_service as data_loader
from app.services.catalog_service import load_pets, load_weapons, validate_site_content
from app.services.exploration.site_combat_service import initial_combat, resolve_turn
from app.tests.factory.dwellers import create_rush_dweller_payload
from app.utils.exceptions import ValidationException
from app.utils.item_factory import build_pet, build_weapon

SITE_IDS = (
    "red_rocket",
    "super_duper_mart",
    "abandoned_campsite",
    "roadside_supply_truck",
    "forgotten_shack",
    "collapsed_subway",
    "rusted_midway",
    "frozen_research_outpost",
    "raider_tollbooth",
    "gloomwater_bog",
    "gloomwater_bog_night",
    "outskirts_interchange",
    "vault_68",
    "vault_69",
)
LEVELS = (5, 10, 15, 20)
WEAPON_TYPES = (None, "melee", "gun", "energy", "heavy")


def _site(site_id: str):
    return data_loader.get_expedition_site(site_id)


def _fight(site, dweller, max_turns: int = 200):
    state = initial_combat(site)
    won = lost = False
    turns = 0
    for _ in range(max_turns):
        state, won, lost, _ = resolve_turn(state, dweller, use_skill=False)
        turns += 1
        if won or lost:
            break
    return state, won, lost, turns


def _sites_for(level: int):
    return [
        site
        for site in data_loader.load_expedition_sites()
        if not site.scenario_only and site.encounter is not None and site.min_dweller_level <= level
    ]


def test_sites_load_and_validate():
    sites = data_loader.load_expedition_sites()
    assert {site.id for site in sites} == set(SITE_IDS)
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


def test_site_shapes_and_offer_weights():
    assert _site("no_such_site") is None
    assert (_site("raider_tollbooth").offer_weight, _site("super_duper_mart").offer_weight) == (2.0, 1.0)
    site = _site("red_rocket")
    assert site is not None
    assert (site.min_dweller_level, [room.id for room in site.rooms]) == (3, ["forecourt", "garage", "bunker"])
    assert (site.rooms[0].node.kind, site.rooms[1].node.kind, site.reward_vault.caps_min) == ("trap", "combat", 80)
    site = _site("super_duper_mart")
    assert site is not None
    assert site.min_dweller_level == 5
    boss = site.rooms[2].node.enemies[0]
    assert (boss.name, boss.min_damage) == ("Raider Boss", 25)
    assert site.reward_vault.item is not None
    assert site.reward_vault.item.floor == "rare"


def test_raider_tollbooth_shape():
    site = _site("raider_tollbooth")
    assert site is not None
    assert site.encounter is not None
    node = site.encounter.node
    assert node.kind == "trivia"
    assert [enemy.arena_key for enemy in node.enemies] == ["raider"]
    assert len(node.trivia_questions) >= 18
    for question in node.trivia_questions:
        assert question.correct_option_id in {option.id for option in question.options}
        assert 1 <= question.difficulty <= 5
    raiders = data_loader.load_trivia_raiders()
    assert {raider.gender for raider in raiders} == {"female", "male"}
    assert len({raider.name for raider in raiders}) == len(raiders)
    assert all(raider.intro and raider.correct_line and raider.wrong_line for raider in raiders)
    assert all(raider.image_url and raider.alt_image_url for raider in raiders)
    assert site.reward_vault.caps_min == 40


@pytest.mark.parametrize(
    ("site_id", "minimum_questions"), [("raider_tollbooth", 18), ("outskirts_interchange", 12), ("rusted_midway", 12)]
)
def test_trivia_sites_have_expanded_question_pools(site_id: str, minimum_questions: int):
    site = _site(site_id)
    assert site is not None
    assert site.encounter is not None
    node = site.encounter.node
    questions = node.trivia_questions
    assert node.kind == "trivia"
    assert len(questions) >= minimum_questions
    assert len({question.id for question in questions}) == len(questions)
    assert all(len(question.options) >= 3 for question in questions)
    assert all(question.correct_option_id in {option.id for option in question.options} for question in questions)
    assert all(1 <= question.difficulty <= 5 for question in questions)


def test_raider_variant_assets_are_shipped_and_transparent():
    static = Path(__file__).resolve().parents[2] / "static"
    site = _site("raider_tollbooth")
    assert site is not None
    assert site.encounter is not None
    for raider in data_loader.load_trivia_raiders():
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


def test_schema_rejections():
    with pytest.raises(ValidationError, match="answer is not one of its options"):
        TriviaQuestion(
            id="q",
            prompt="?",
            difficulty=2,
            options=[TriviaOption(id="a", label="A"), TriviaOption(id="b", label="B")],
            correct_option_id="c",
        )
    site = _site("raider_tollbooth").model_copy(deep=True)
    site.encounter.node.trivia_questions = []
    with pytest.raises(ValidationException, match="needs trivia questions"):
        validate_site_content(site)
    raiders = data_loader.load_trivia_raiders()
    with pytest.raises(ValidationError, match="unique ids and names"):
        ExpeditionSiteList(sites=[], trivia_raiders=[raiders[0], raiders[0]])
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
    "site", [site for site in data_loader.load_expedition_sites() if not site.scenario_only], ids=lambda s: s.id
)
def test_scene_rosters_and_intro_balance(site):
    # A modest unarmed dweller is a deliberately conservative first-release baseline.
    dweller = Dweller(**create_rush_dweller_payload(strength=3), level=site.min_dweller_level, radiation=0)
    _, won, lost, _turns = _fight(site, dweller, max_turns=160)
    assert won
    assert not lost
    assert dweller.health >= 60


@pytest.mark.parametrize(
    ("problem", "error"),
    [
        ("desert", "does not belong"),
        ("missing_scene", None),
        ("choice_encounter", None),
        ("empty_roster", None),
        ("wrong_pool", None),
    ],
)
def test_encounter_authoring_errors_are_rejected_at_validation(problem, error):
    site = _site("roadside_supply_truck").model_copy(deep=True)
    if problem == "desert":
        site = _site("roadside_supply_truck").model_copy(update={"scene_id": "arctic_research_station"})
    elif problem == "missing_scene":
        site.scene_id = None
    elif problem == "choice_encounter":
        site.encounter.node.kind = "choice"
    elif problem == "empty_roster":
        site.encounter.node.enemies = []
    else:
        site.scene_id = "arctic_research_station"
    if error is None:
        with pytest.raises(ValidationException):
            validate_site_content(site)
    else:
        with pytest.raises(ValidationException, match=error):
            validate_site_content(site)


def test_catalog_rejects_invalid_encounter_before_returning_sites(tmp_path, monkeypatch):
    site = _site("roadside_supply_truck").model_dump(mode="json")
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


def _matrix_dweller(level: int, weapon_type: str | None):
    hp = 100 + 5 * (level - 1)
    payload = create_rush_dweller_payload(strength=5, luck=5, intelligence=5) | {
        "level": level,
        "max_health": hp,
        "health": hp,
        "radiation": 0,
        "perception": 5,
        "endurance": 5,
        "charisma": 5,
        "agility": 5,
    }
    dweller = Dweller(**payload)
    if weapon_type is not None:
        candidates = [w for w in load_weapons() if str(w.get("weapon_type", "")).lower() == weapon_type]
        data = candidates[len(candidates) // 2]
        dweller.weapon = build_weapon(data, data["rarity"])
    return dweller


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("weapon_type", WEAPON_TYPES)
def test_scene_balance_matrix(level, weapon_type):
    dweller = _matrix_dweller(level, weapon_type)
    for site in _sites_for(level):
        dweller.health = dweller.effective_max_health
        state, won, lost, turns = _fight(site, dweller)
        label = f"{site.id} level={level} weapon={weapon_type}"
        assert won, f"{label}: lost"
        assert dweller.health >= 0.6 * dweller.max_health, f"{label}: health {dweller.health}"
        assert turns <= 20, f"{label}: {turns} turns"
        damages = [
            int(event["message"].rsplit(" for ", 1)[1]) for event in state["events"] if " for " in event["message"]
        ]
        assert max(damages) > 1, f"{label}: damage still 1"


@pytest.mark.parametrize("level", [5, 20])
def test_scene_balance_with_equipped_pet(level):
    dweller = _matrix_dweller(level, "gun")
    data = load_pets()[0]
    dweller.pet = build_pet(data, data["rarity"])
    for site in _sites_for(level):
        dweller.health = dweller.effective_max_health
        _, won, lost, _turns = _fight(site, dweller)
        assert won
        assert not lost
        assert dweller.health >= 0.6 * dweller.max_health
