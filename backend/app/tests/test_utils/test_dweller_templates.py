import random

import pytest

from app.core.game_config import game_config
from app.schemas.common import RarityEnum
from app.schemas.dweller import DwellerTemplate
from app.utils.dwellers import create_dweller_from_template
from app.utils.places import GENERIC_ORIGIN_SKIP, normalize_place_name
from app.utils.static_data import game_data_store


def test_all_templates_load() -> None:
    dwellers = game_data_store.dwellers
    assert len(dwellers) == 55
    assert all(isinstance(d, DwellerTemplate) for d in dwellers)


def test_templates_have_legal_rarity() -> None:
    for d in game_data_store.dwellers:
        assert str(d.rarity).lower() in {"common", "rare", "legendary"}


def test_pick_template_returns_correct_rarity() -> None:
    rng = random.Random(42)
    rare = game_data_store.pick_template("rare", rng=rng)
    assert rare is not None
    assert str(rare.rarity).lower() == "rare"
    legendary = game_data_store.pick_template("legendary", rng=rng)
    assert legendary is not None
    assert str(legendary.rarity).lower() == "legendary"


def test_pick_template_excludes_names() -> None:
    first = game_data_store.pick_template("legendary", rng=random.Random(1))
    assert first is not None
    name = f"{first.first_name} {first.last_name or ''}".strip()
    second = game_data_store.pick_template("legendary", rng=random.Random(1), exclude_names={name})
    assert second is None or f"{second.first_name} {second.last_name or ''}".strip().casefold() != name.casefold()


def test_pick_template_exhaustion_returns_none() -> None:
    names = {f"{d.first_name} {d.last_name or ''}".strip() for d in game_data_store.get_dwellers_by_rarity("rare")}
    assert game_data_store.pick_template("rare", exclude_names=names) is None


def test_to_create_payload_preserves_metadata() -> None:
    t = DwellerTemplate.model_validate(
        {
            "first_name": "Test",
            "last_name": "Vault",
            "template_id": "test-vault",
            "gender": "Male",
            "rarity": "Rare",
            "strength": 5,
            "perception": 5,
            "endurance": 5,
            "charisma": 5,
            "intelligence": 5,
            "agility": 5,
            "luck": 5,
            "origin_place": "Rivet City",
            "visited_places": ["Megaton", "Tenpenny Tower"],
            "bio": "Grew up in Rivet City.",
            "visual_attributes": {"race": "human", "faction": "vault_dweller"},
        }
    )
    payload, origin, visited = t.to_create_payload()
    assert origin == "Rivet City"
    assert visited == ["Megaton", "Tenpenny Tower"]
    assert payload.first_name == "Test"
    assert payload.bio == "Grew up in Rivet City."


def _template_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "first_name": "Test",
        "last_name": "Vault",
        "template_id": "test-vault",
        "gender": "Male",
        "rarity": "Rare",
        "strength": 5,
        "perception": 5,
        "endurance": 5,
        "charisma": 5,
        "intelligence": 5,
        "agility": 5,
        "luck": 5,
        "origin_place": "Rivet City",
        "visited_places": ["Megaton"],
        "bio": "Grew up in Rivet City.",
        "visual_attributes": {"race": "human", "faction": "vault_dweller"},
    }
    base.update(overrides)
    return base


def test_template_trims_and_drops_blank_visited() -> None:
    t = DwellerTemplate.model_validate(_template_payload(visited_places=["  Megaton  ", "   ", ""]))
    assert t.visited_places == ["Megaton"]


def test_template_rejects_duplicate_normalized_visited() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        DwellerTemplate.model_validate(_template_payload(visited_places=["Megaton", "megaton"]))


def test_template_rejects_visited_matching_origin() -> None:
    with pytest.raises(ValueError, match="origin"):
        DwellerTemplate.model_validate(_template_payload(visited_places=["rivet city"]))


def test_template_rejects_more_than_four_visited() -> None:
    with pytest.raises(ValueError, match="at most 4"):
        DwellerTemplate.model_validate(
            _template_payload(visited_places=["Megaton", "Arefu", "Big Town", "Concord", "Covenant"])
        )


def test_template_rejects_blank_origin() -> None:
    with pytest.raises(ValueError, match="origin_place"):
        DwellerTemplate.model_validate(_template_payload(origin_place="   "))


def test_create_dweller_from_template_uses_curated_special() -> None:
    t = game_data_store.pick_template("legendary", rng=random.Random(0))
    assert t is not None
    data = create_dweller_from_template(t, seed=123)
    assert data["strength"] == t.strength
    assert data["perception"] == t.perception
    assert data["rarity"] == t.rarity


def test_companion_template_allows_null_visuals() -> None:
    t = DwellerTemplate.model_validate(
        {
            "first_name": "CX404",
            "last_name": "",
            "template_id": "cx404",
            "gender": "Male",
            "rarity": "Legendary",
            "strength": 5,
            "perception": 7,
            "endurance": 7,
            "charisma": 6,
            "intelligence": 4,
            "agility": 9,
            "luck": 6,
            "origin_place": "Filly",
            "visited_places": [],
            "visual_attributes": None,
            "bio": "A loyal canine companion.",
        }
    )
    assert t.visual_attributes is None
    data = create_dweller_from_template(t)
    assert data["visual_attributes"] is None


def test_template_rejects_invalid_visual_identity() -> None:
    with pytest.raises(ValueError, match="not valid for race"):
        DwellerTemplate.model_validate(
            {
                "first_name": "Invalid",
                "last_name": "Identity",
                "template_id": "invalid-identity",
                "gender": "Male",
                "rarity": "Rare",
                "strength": 5,
                "perception": 5,
                "endurance": 5,
                "charisma": 5,
                "intelligence": 5,
                "agility": 5,
                "luck": 5,
                "origin_place": "Megaton",
                "visited_places": [],
                "visual_attributes": {"race": "human", "faction": "super_mutant_tribe"},
            }
        )


def test_all_templates_have_required_metadata() -> None:
    companions = {("snip", "snip"), ("cx404", "")}
    for d in game_data_store.dwellers:
        name = f"{d.first_name} {d.last_name or ''}".strip()
        is_companion = (d.first_name.casefold(), (d.last_name or "").casefold()) in companions
        assert d.bio is not None, f"{name} missing bio"
        assert d.bio.strip(), f"{name} blank bio"
        assert len(d.bio) <= 1024, f"{name} bio too long {len(d.bio)}"
        assert d.origin_place.strip(), f"{name} missing origin_place"
        if is_companion:
            assert d.visual_attributes is None, f"{name} companion should have null visuals"
        else:
            assert d.visual_attributes is not None, f"{name} missing visual_attributes"
            assert d.visual_attributes.race is not None, f"{name} visual_attributes missing race"
            assert d.visual_attributes.faction is not None, f"{name} visual_attributes missing faction"


def test_visited_place_caps_and_deduplication() -> None:
    for d in game_data_store.dwellers:
        name = f"{d.first_name} {d.last_name or ''}".strip()
        max_visited = game_config.bio.max_visited(str(d.rarity).lower())
        assert len(d.visited_places or []) <= max_visited, f"{name} visited_places exceeds cap {max_visited}"
        if not d.visited_places:
            continue
        normalized = [normalize_place_name(p) for p in d.visited_places]
        assert len(normalized) == len(set(normalized)), f"{name} visited_places has duplicates"
        assert all(n not in GENERIC_ORIGIN_SKIP for n in normalized), f"{name} visited_places contains generic skip"
        origin_norm = normalize_place_name(d.origin_place or "")
        assert origin_norm not in normalized, f"{name} origin appears in visited_places"
        assert all(p.strip() for p in d.visited_places), f"{name} visited place blank"
        assert all(len(p.strip()) <= 64 for p in d.visited_places), f"{name} visited place too long"
        assert d.origin_place.strip(), f"{name} origin blank"
        assert len(d.origin_place.strip()) <= 64, f"{name} origin too long"


def test_bio_mentions_origin_and_visited_places() -> None:
    for d in game_data_store.dwellers:
        name = f"{d.first_name} {d.last_name or ''}".strip()
        bio_lower = (d.bio or "").lower()
        assert d.origin_place.lower() in bio_lower, f"{name} bio does not mention origin_place {d.origin_place!r}"
        for place in d.visited_places or []:
            assert place.lower() in bio_lower, f"{name} bio does not mention visited place {place!r}"


def test_templates_have_legal_special_and_visual_identity() -> None:
    for d in game_data_store.dwellers:
        name = f"{d.first_name} {d.last_name or ''}".strip()
        for stat in ("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"):
            val = getattr(d, stat)
            assert 1 <= val <= 10, f"{name} {stat}={val} out of bounds"
        va = d.visual_attributes
        if va is None:
            continue
        assert va is not None
        # DwellerTemplate already validates race/faction combo via DwellerVisualAttributes


def test_roster_has_unique_template_names() -> None:
    names = [f"{d.first_name} {d.last_name or ''}".strip().casefold() for d in game_data_store.dwellers]
    assert len(names) == len(set(names)), "duplicate template names found (case-insensitive)"


def test_backfill_registry_covers_template_places() -> None:
    from app.services.bio_place_backfill_service import _KNOWN_ORIGIN_PLACES, _KNOWN_VISITED_PLACES

    origin_set = {normalize_place_name(p) for p in _KNOWN_ORIGIN_PLACES}
    visited_set = {normalize_place_name(p.strip()) for p in _KNOWN_VISITED_PLACES}
    for d in game_data_store.dwellers:
        origin_norm = normalize_place_name(d.origin_place or "")
        # Template origins are registered explicitly at runtime; the registry only
        # powers free-text backfill recovery. An origin may therefore also live in
        # the visited list (e.g. Far Harbor, which backfill tests pin as visited-only).
        assert origin_norm in origin_set or origin_norm in visited_set, (
            f"{d.first_name} origin {d.origin_place!r} not in backfill registries"
        )
        for place in d.visited_places or []:
            assert normalize_place_name(place) in visited_set, (
                f"{d.first_name} visited {place!r} not in backfill visited registry"
            )
