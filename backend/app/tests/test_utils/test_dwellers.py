"""Tests for dweller bio generation utilities."""

import random
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.core.game_config import DwellerConfig, game_config
from app.options.bios import render_bio, render_newborn_bio
from app.options.factions import faction_restrictions
from app.options.races import STATE_OF_BEING_VALUES, RaceOption
from app.schemas.common import AgeGroupEnum, RarityEnum
from app.utils.dwellers import (
    _PLACE_POOL,
    _calendar_years_ago,
    _procedural_bio_places,
    create_random_common_dweller,
)


def test_place_pool_has_no_unregistrable_names() -> None:
    """Every pool name must survive map registration (none in the origin skip list)."""
    from app.utils.places import GENERIC_ORIGIN_SKIP

    normalized = {name.strip().lower() for name in GENERIC_ORIGIN_SKIP}
    for place in _PLACE_POOL:
        assert place.strip().lower() not in normalized


def test_render_template_bio_no_visited() -> None:
    assert render_bio("Megaton", [], race=RaceOption.HUMAN) == (
        "Born in Megaton. Before the vault, I wandered the wastes alone."
    )


def test_render_template_bio_single_visited() -> None:
    assert render_bio("Megaton", ["Rivet City"], race=None) == (
        "Born in Megaton. Before the vault, I wandered through Rivet City."
    )


@pytest.mark.parametrize(
    ("race", "marker"),
    [
        (RaceOption.GHOUL, "before the bombs"),
        (RaceOption.SYNTH, "I was not born"),
        (RaceOption.SUPER_MUTANT, "vats"),
    ],
)
def test_render_bio_non_human_voice(race: RaceOption, marker: str) -> None:
    """Non-human bios frame the shared origin pool in a lore-safe way."""
    rng = random.Random(7)
    visited = render_bio("Megaton", ["Rivet City", "Diamond City"], race=race, rng=rng)
    assert marker in visited
    assert "Rivet City" in visited
    assert "Diamond City" in visited
    assert "Born in Megaton" not in visited

    assert "Born in Megaton" not in render_bio("Megaton", [], race=race, rng=rng)


def test_procedural_bio_places_scales_with_rarity() -> None:
    """Visited counts stay tight: 1/2/3 for common/rare/legendary."""
    assert len(_procedural_bio_places(random.Random(3), RarityEnum.COMMON)[1]) == 1
    assert len(_procedural_bio_places(random.Random(3), RarityEnum.RARE)[1]) == 2
    assert len(_procedural_bio_places(random.Random(3), RarityEnum.LEGENDARY)[1]) == 3


def test_create_random_common_dweller_state_of_being_for_non_humans() -> None:
    """Non-humans carry a state_of_being from STATE_OF_BEING_OPTIONS; humans carry none."""
    for seed in range(300):
        attrs = create_random_common_dweller(seed=seed)["visual_attributes"]
        race = RaceOption(attrs["race"])
        if race == RaceOption.HUMAN:
            assert "state_of_being" not in attrs
        else:
            assert attrs["state_of_being"] in STATE_OF_BEING_VALUES[race]


def test_dweller_config_race_weights_rejects_unknown_key() -> None:
    with pytest.raises(ValueError, match="Unknown race"):
        DwellerConfig(race_weights={"human": 70, "ghoul": 15, "synth": 10, "super_mutant": 5, "robot": 10})


def test_dweller_config_race_weights_rejects_missing_race() -> None:
    with pytest.raises(ValueError, match="missing"):
        DwellerConfig(race_weights={"human": 70, "ghoul": 30})


def test_dweller_config_race_weights_rejects_negative_and_non_int() -> None:
    with pytest.raises(ValueError, match="integer"):
        DwellerConfig(race_weights={"human": 70, "ghoul": 15, "synth": 10, "super_mutant": -5})
    with pytest.raises(ValueError, match="integer"):
        DwellerConfig(race_weights={"human": 70.5, "ghoul": 15, "synth": 10, "super_mutant": 5})


def test_dweller_config_race_weights_rejects_zero_total() -> None:
    with pytest.raises(ValueError, match="positive total"):
        DwellerConfig(race_weights={"human": 0, "ghoul": 0, "synth": 0, "super_mutant": 0})


def test_dweller_config_human_faction_weights_policy() -> None:
    """human_faction_weights: vault_dweller dominant, keys within human faction_restrictions."""
    weights = game_config.dweller.human_faction_weights
    assert weights["vault_dweller"] == max(weights.values())
    assert set(weights) <= {faction.value for faction in faction_restrictions[RaceOption.HUMAN]}


def test_vault_start_config_rare_chances() -> None:
    """Standard seeding stays at 4% RARE; boosted vaults get the 12% P0 boost."""
    assert game_config.vault_start.standard_rare_chance == 0.04
    assert game_config.vault_start.boosted_rare_chance == 0.12


def test_crafting_config_rejects_incomplete_junk_recipe() -> None:
    """A recipe without every craftable rarity would KeyError on the common fallback."""
    from app.core.game_config import CraftingConfig

    with pytest.raises(ValidationError, match="missing rarities"):
        CraftingConfig(junk_recipe_by_rarity={"common": {"common": 3}, "rare": {"common": 3, "rare": 3}})


def test_crafting_config_rejects_unknown_material_rarity() -> None:
    from app.core.game_config import CraftingConfig

    with pytest.raises(ValidationError, match="Unknown material rarities"):
        CraftingConfig(
            junk_recipe_by_rarity={
                "common": {"common": 3},
                "rare": {"common": 3, "rare": 3},
                "legendary": {"common": 3, "rare": 3, "legendary": 3, "mythic": 1},
            }
        )


def test_crafting_config_rejects_negative_material_counts() -> None:
    """A negative count would consume the wrong junk."""
    from app.core.game_config import CraftingConfig

    with pytest.raises(ValidationError, match="non-negative"):
        CraftingConfig(
            junk_recipe_by_rarity={
                "common": {"common": -1},
                "rare": {"common": 3, "rare": 3},
                "legendary": {"common": 3, "rare": 3, "legendary": 3},
            }
        )


def test_crafting_config_normalizes_rarity_keys() -> None:
    from app.core.game_config import CraftingConfig

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


def test_render_newborn_bio_links_both_parents(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.options import bios

    monkeypatch.setattr(bios, "NEWBORN_BIO_TEMPLATES", ("{mother} and {father}.",))

    bio = render_newborn_bio("Jane", "John", "m-1", "f-1", "v-1")

    assert 'href="/vault/v-1/dwellers/m-1"' in bio
    assert 'href="/vault/v-1/dwellers/f-1"' in bio
    assert "Jane" in bio
    assert "John" in bio


def test_render_newborn_bio_escapes_parent_names(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.options import bios

    monkeypatch.setattr(bios, "NEWBORN_BIO_TEMPLATES", ("{mother} {father}",))

    bio = render_newborn_bio("<script>alert(1)</script>", "John", "m-1", "f-1", "v-1")

    assert "<script>" not in bio
    assert "&lt;script&gt;" in bio


def test_render_newborn_bio_never_injects_parent_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every authored template must escape a hostile name, placeholders or not."""
    from app.options import bios

    for template in bios.NEWBORN_BIO_TEMPLATES:
        monkeypatch.setattr(bios, "NEWBORN_BIO_TEMPLATES", (template,))
        bio = render_newborn_bio("<script>x</script>", "<b>John</b>", "m-1", "f-1", "v-1")
        assert "<script>" not in bio
        assert "<b>" not in bio
