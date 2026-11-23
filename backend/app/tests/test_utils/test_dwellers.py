import random
from collections import Counter
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.core.enums import AgeGroupEnum, RarityEnum
from app.core.game_config import CraftingConfig, DwellerConfig, game_config
from app.options import bios as bios_catalog
from app.options.bios import ZONE_RUMORS
from app.options.factions import faction_restrictions
from app.options.races import STATE_OF_BEING_VALUES, RaceOption
from app.utils import bios
from app.utils.bios import maybe_zone_rumor, render_adopted_child_bio, render_bio, render_newborn_bio
from app.utils.dwellers import (
    _PLACE_POOL,
    _calendar_years_ago,
    _identity_for_race,
    _procedural_bio_places,
    _roll_identity,
    create_dweller_from_template,
    create_random_common_dweller,
    roll_spawn_birth_date,
)
from app.utils.places import GENERIC_ORIGIN_SKIP
from app.utils.static_data import game_data_store


def test_place_pool_has_no_unregistrable_names() -> None:
    normalized = {name.strip().lower() for name in GENERIC_ORIGIN_SKIP}
    for place in _PLACE_POOL:
        assert place.strip().lower() not in normalized


def test_render_template_bios() -> None:
    assert render_bio("Megaton", [], race=RaceOption.HUMAN) == (
        "Born in Megaton. Before the vault, I wandered the wastes alone."
    )
    assert render_bio("Megaton", ["Rivet City"], race=None) == (
        "Born in Megaton. Before the vault, I wandered through Rivet City."
    )


@pytest.mark.parametrize(
    ("race", "marker"),
    [(RaceOption.GHOUL, "before the bombs"), (RaceOption.SYNTH, "I was not born"), (RaceOption.SUPER_MUTANT, "vats")],
)
def test_render_bio_non_human_voice(race: RaceOption, marker: str) -> None:
    rng = random.Random(7)
    visited = render_bio("Megaton", ["Rivet City", "Diamond City"], race=race, rng=rng)
    assert marker in visited
    assert "Rivet City" in visited
    assert "Diamond City" in visited
    assert "Born in Megaton" not in visited
    assert "Born in Megaton" not in render_bio("Megaton", [], race=race, rng=rng)


@pytest.mark.parametrize(("rarity", "count"), [(RarityEnum.COMMON, 0), (RarityEnum.RARE, 1), (RarityEnum.LEGENDARY, 2)])
def test_procedural_bio_places_scales_with_rarity(rarity: RarityEnum, count: int) -> None:
    assert len(_procedural_bio_places(random.Random(3), rarity)[1]) == count


def test_starting_progression_matches_rarity_band() -> None:
    cfg = game_config.leveling
    assert create_random_common_dweller(seed=1, rarity=RarityEnum.COMMON)["level"] == 1
    for seed in range(25):
        rare = create_random_common_dweller(seed=seed, rarity=RarityEnum.RARE)
        legendary = create_random_common_dweller(seed=seed, rarity=RarityEnum.LEGENDARY)
        assert cfg.rare_start_level_min <= rare["level"] <= cfg.rare_start_level_max
        assert cfg.legendary_start_level_min <= legendary["level"] <= cfg.legendary_start_level_max
        for dweller in (rare, legendary):
            level = dweller["level"]
            assert dweller["max_health"] == cfg.base_max_health + (level - 1) * cfg.hp_gain_per_level
            assert dweller["health"] == dweller["max_health"]
            expected_xp = 0 if level <= 1 else int(cfg.base_xp_requirement * (level**cfg.xp_curve_exponent))
            assert dweller["experience"] == expected_xp
            assert dweller["experience"] < int(cfg.base_xp_requirement * ((level + 1) ** cfg.xp_curve_exponent))

    template = game_data_store.get_dweller("abraham-washington")
    assert template is not None
    data = create_dweller_from_template(template, seed=1)
    assert cfg.legendary_start_level_min <= data["level"] <= cfg.legendary_start_level_max
    assert data["max_health"] == cfg.base_max_health + (data["level"] - 1) * cfg.hp_gain_per_level
    assert data["experience"] == int(cfg.base_xp_requirement * (data["level"] ** cfg.xp_curve_exponent))


def test_create_random_common_dweller_states_and_elders() -> None:
    seeded_now = datetime(2000, 1, 1)
    threshold = _calendar_years_ago(seeded_now, game_config.dweller.elder_age_years)
    groups = set()
    for seed in range(300):
        dweller = create_random_common_dweller(seed=seed)
        attrs = dweller["visual_attributes"]
        race = RaceOption(attrs["race"])
        if race == RaceOption.HUMAN:
            assert "state_of_being" not in attrs
            expected = AgeGroupEnum.ELDER if dweller["birth_date"] <= threshold else AgeGroupEnum.ADULT
        else:
            assert attrs["state_of_being"] in STATE_OF_BEING_VALUES[race]
            expected = AgeGroupEnum.ADULT
        assert dweller["age_group"] == expected
        groups.add(dweller["age_group"])
    assert groups == {AgeGroupEnum.ADULT, AgeGroupEnum.ELDER}


def test_spawn_birth_dates_lean_under_thirty() -> None:
    now = datetime(2000, 1, 1)
    ages = [(now - roll_spawn_birth_date(now, random.Random(seed))).days // 365 for seed in range(1000)]
    assert sum(1 for age in ages if age < 30) / len(ages) > 0.6
    assert sum(1 for age in ages if age >= game_config.dweller.elder_age_years) / len(ages) < 0.1


@pytest.mark.parametrize(
    ("recipe", "match"),
    [
        ({"common": {"common": 3}, "rare": {"common": 3, "rare": 3}}, "missing rarities"),
        (
            {
                "common": {"common": 3},
                "rare": {"common": 3, "rare": 3},
                "legendary": {"common": 3, "rare": 3, "legendary": 3, "mythic": 1},
            },
            "Unknown material rarities",
        ),
    ],
)
def test_crafting_config_rejects_invalid_recipes(recipe: dict, match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        CraftingConfig(junk_recipe_by_rarity=recipe)


def test_crafting_config_material_rules() -> None:
    with pytest.raises(ValidationError) as exc:
        CraftingConfig(
            junk_recipe_by_rarity={
                "common": {"common": -1},
                "rare": {"common": 3, "rare": 3},
                "legendary": {"common": 3, "rare": 3, "legendary": 3},
            }
        )
    assert exc.value.errors()[0]["loc"] == ("junk_recipe_by_rarity", "common", "common")
    config = CraftingConfig(
        junk_recipe_by_rarity={
            "Common": {"Common": 3},
            "RARE": {"common": 3, "rare": 3},
            "legendary": {"common": 3, "rare": 3, "legendary": 3},
        }
    )
    assert config.junk_recipe("rare") == {"common": 3, "rare": 3}
    assert config.junk_cost("rare") == 6
    assert config.junk_cost("unknown") == 3


def test_child_bios_link_and_escape_parent_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bios, "NEWBORN_BIO_TEMPLATES", ("{mother} and {father}.",))
    bio = render_newborn_bio("Jane", "John", "m-1", "f-1", "v-1")
    assert bio == (
        '<a href="/vault/v-1/dwellers/m-1" class="dweller-link">Jane</a> and '
        '<a href="/vault/v-1/dwellers/f-1" class="dweller-link">John</a>.'
    )
    monkeypatch.setattr(bios, "NEWBORN_BIO_TEMPLATES", ("{mother} {father}",))
    escaped = render_newborn_bio("<script>alert(1)</script>", "John", "m-1", "f-1", "v-1")
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped
    for template in bios_catalog.NEWBORN_BIO_TEMPLATES:
        monkeypatch.setattr(bios, "NEWBORN_BIO_TEMPLATES", (template,))
        rendered = render_newborn_bio("<script>x</script>", "<b>John</b>", "m-1", "f-1", "v-1")
        assert "<script>" not in rendered
        assert "<b>" not in rendered


def test_render_adopted_child_bio_links_and_escapes_parent_names() -> None:
    bio = render_adopted_child_bio("<script>x</script>", "John", "p-1", "p-2", "v-1")
    assert "adopted" in bio
    assert 'href="/vault/v-1/dwellers/p-1"' in bio
    assert 'href="/vault/v-1/dwellers/p-2"' in bio
    assert "<script>" not in bio
    assert "&lt;script&gt;" in bio


def test_maybe_zone_rumor_hits_and_misses() -> None:
    assert maybe_zone_rumor(random.Random(1), 0.0) is None
    assert maybe_zone_rumor(random.Random(1), 1.0) in ZONE_RUMORS


@pytest.mark.parametrize(("chance", "expected"), [(0.0, 0), (1.0, 1)])
def test_zone_rumor_chance_reaches_generated_bios(
    monkeypatch: pytest.MonkeyPatch, chance: float, expected: int
) -> None:
    monkeypatch.setattr(game_config.bio, "zone_rumor_chance", chance)
    for seed in range(25):
        bio = create_random_common_dweller(seed=seed)["bio"]
        assert sum(rumor in bio for rumor in ZONE_RUMORS) == expected


def test_zone_rumor_generation_is_seed_reproducible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(game_config.bio, "zone_rumor_chance", 1.0)
    assert create_random_common_dweller(seed=99)["bio"] == create_random_common_dweller(seed=99)["bio"]
    origin, visited = create_random_common_dweller(seed=7)["_bio_places"]
    assert "The Quiet Zone" not in visited
    assert origin != "The Quiet Zone"


def _state_weight_defaults() -> dict[str, dict[str, int]]:
    return {
        "ghoul": {"sane": 70, "wild": 22, "feral": 8},
        "super_mutant": {"mild": 55, "average": 35, "behemoth": 10},
        "synth": {"gen_3": 70, "gen_2": 22, "gen_1": 8},
    }


def test_default_weights_keep_non_humans_rare_and_human_like() -> None:
    weights = game_config.dweller.get_race_weights()
    assert weights == {"human": 85, "ghoul": 7, "synth": 5, "super_mutant": 3}
    assert weights["human"] / sum(weights.values()) >= 0.85
    ghoul = game_config.dweller.get_state_weights("ghoul")
    mutant = game_config.dweller.get_state_weights("super_mutant")
    synth = game_config.dweller.get_state_weights("synth")
    assert ghoul["sane"] > ghoul["wild"] > ghoul["feral"]
    assert mutant["mild"] > mutant["average"] > mutant["behemoth"]
    assert synth["gen_3"] > synth["gen_2"] > synth["gen_1"]
    faction_weights = game_config.dweller.human_faction_weights
    assert faction_weights["vault_dweller"] == max(faction_weights.values())
    assert set(faction_weights) <= {faction.value for faction in faction_restrictions[RaceOption.HUMAN]}
    assert game_config.vault_start.standard_rare_chance == 0.04
    assert game_config.vault_start.boosted_rare_chance == 0.12


def test_identity_rolls_keep_human_like_states_and_races() -> None:
    for race, expected in [(RaceOption.GHOUL, "sane"), (RaceOption.SUPER_MUTANT, "mild"), (RaceOption.SYNTH, "gen_3")]:
        rng = random.Random(0)
        counts = Counter(_identity_for_race(race, rng)["state_of_being"] for _ in range(600))
        assert counts.most_common(1)[0][0] == expected
    races_rng = random.Random(0)
    races = Counter(_roll_identity(races_rng)["race"] for _ in range(1000))
    assert races["human"] > 800
    assert races["ghoul"] > races["synth"] > races["super_mutant"]


RACE_WEIGHT_CASES = [
    (
        lambda: DwellerConfig(race_weights={"human": 70, "ghoul": 15, "synth": 10, "super_mutant": 5, "robot": 10}),
        "Unknown race",
    ),
    (lambda: DwellerConfig(race_weights={"human": 70, "ghoul": 30}), "missing"),
    (lambda: DwellerConfig(race_weights={"human": 70, "ghoul": 15, "synth": 10, "super_mutant": -5}), "integer"),
    (lambda: DwellerConfig(race_weights={"human": 70.5, "ghoul": 15, "synth": 10, "super_mutant": 5}), "integer"),
    (lambda: DwellerConfig(race_weights={"human": 0, "ghoul": 0, "synth": 0, "super_mutant": 0}), "positive total"),
]
STATE_WEIGHT_CASES = [
    (lambda w: w.pop("synth"), "missing races"),
    (lambda w: w["ghoul"].update(decayed=1), "Unknown state"),
    (lambda w: w["ghoul"].pop("feral"), "missing states"),
    (lambda w: w["ghoul"].update(sane=-1), "non-negative integer"),
    (lambda w: w.update(ghoul={"sane": 0, "wild": 0, "feral": 0}), "positive total"),
]


def test_dweller_config_rejects_invalid_weights() -> None:
    for build, match in RACE_WEIGHT_CASES:
        with pytest.raises(ValueError, match=match):
            build()
    for mutate, match in STATE_WEIGHT_CASES:
        weights = _state_weight_defaults()
        mutate(weights)
        with pytest.raises(ValueError, match=match):
            DwellerConfig(state_weights=weights)
