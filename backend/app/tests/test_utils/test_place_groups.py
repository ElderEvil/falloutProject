import json

import pytest

from app.core.enums import PlaceKindEnum
from app.core.game_config import game_config
from app.utils.place_groups import (
    DEFAULT_EMERGENT_GROUP,
    GROUPS_FILE,
    effective_place_group,
    get_place_group,
    group_for_place_name,
    load_place_groups,
    place_groups_by_key,
    seeded_place_groups,
    validate_group_key,
)

CLEARABLE_GROUPS = {
    "gas_station",
    "supermarket",
    "factory",
    "metro",
    "military",
    "brotherhood_outpost",
    "research",
    "power",
    "entertainment",
    "vault_tec",
    "ruin",
    "exclusion_zone",
    "wasteland_site",
    "observation_facility",
    "vertical_refuge",
}
NON_CLEARABLE_GROUPS = {"settlement", "city", "landmark", "region"}
MUTATIONS = [
    (lambda gs: next(g for g in gs if g["key"] == "gas_station").pop("reclear_hours"), "reclear_hours"),
    (
        lambda gs: next(g for g in gs if g["key"] == "gas_station").update(loot_table="not_a_table"),
        "unknown loot table",
    ),
    (lambda gs: next(g for g in gs if g["key"] == "gas_station").pop("xp_reward"), "xp_reward"),
    (lambda gs: next(g for g in gs if g["key"] == "settlement").update(xp_reward=10), "must not carry xp_reward"),
    (
        lambda gs: next(g for g in gs if g["key"] == "settlement").update(reclear_hours=48),
        "must not carry reclear_hours",
    ),
]


def _groups() -> dict[str, dict]:
    return {group["key"]: group for group in load_place_groups()}


def test_catalog_is_valid_and_names_resolve_to_their_group() -> None:
    groups = load_place_groups()
    keys = {group["key"] for group in groups}
    assert {"gas_station", "supermarket", "settlement", "vault_tec"} <= keys
    for group in groups:
        assert group["label"]
        assert group["description"]
        assert group["icon"]
    seeded = seeded_place_groups()
    assert set(seeded.values()) <= keys
    by_group: dict[str, list[str]] = {}
    for name, key in seeded.items():
        by_group.setdefault(key, []).append(name)
    assert len(by_group["gas_station"]) >= 3
    assert len(by_group["supermarket"]) >= 2
    assert group_for_place_name("Red Rocket") == "gas_station"
    assert group_for_place_name("  RED ROCKET ") == "gas_station"
    assert group_for_place_name("Super Duper Mart") == "supermarket"
    assert group_for_place_name("The Quiet Zone") == "exclusion_zone"
    assert group_for_place_name("An Emergent Place") is None
    for key, label in (("exclusion_zone", "Restricted Exclusion Site"), ("gas_station", "Gas Station")):
        entry = get_place_group(key)
        assert entry is not None
        assert entry["label"] == label
    assert get_place_group(None) is None
    assert get_place_group("not_a_group") is None


def test_groups_carry_appropriate_clear_fields() -> None:
    assert validate_group_key("gas_station") == "gas_station"
    with pytest.raises(ValueError, match="Unknown place group"):
        validate_group_key("not_a_group")
    groups = _groups()
    assert set(groups) == CLEARABLE_GROUPS | NON_CLEARABLE_GROUPS
    for key in CLEARABLE_GROUPS:
        group = groups[key]
        assert group["clearable"] is True
        assert isinstance(group["reclear_hours"], int)
        assert group["reclear_hours"] >= 1
        assert isinstance(group["base_difficulty"], int)
        assert group["base_difficulty"] >= 1
        assert isinstance(group["loot_table"], str)
        assert group["loot_table"]
    for key in NON_CLEARABLE_GROUPS:
        group = groups[key]
        assert group["clearable"] is False
        assert group.get("reclear_hours") is None
        assert group.get("base_difficulty") is None
        assert group.get("loot_table") is None
        assert group.get("xp_reward") is None
    groups = {key: group for key, group in groups.items() if group["clearable"]}
    for group in groups.values():
        assert isinstance(group["xp_reward"], int)
        assert group["xp_reward"] >= 0
        assert group["reclear_hours"] >= 48
        assert group["base_difficulty"] == {"low": 2, "medium": 3, "high": 4}[group["risk"]]

    def per_hour(key: str) -> float:
        return groups[key]["xp_reward"] / groups[key]["reclear_hours"]

    assert per_hour("wasteland_site") < per_hour("gas_station") < per_hour("military")
    assert per_hour("research") > per_hour("factory")


def _write_groups(tmp_path, groups: list[dict]) -> pytest.MonkeyPatch:
    scratch = tmp_path / "place_groups.json"
    scratch.write_text(json.dumps(groups), encoding="utf-8")
    load_place_groups.cache_clear()
    place_groups_by_key.cache_clear()
    seeded_place_groups.cache_clear()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("app.utils.place_groups.GROUPS_FILE", scratch)
    return monkeypatch


@pytest.mark.parametrize(("mutate", "match"), MUTATIONS)
def test_invalid_group_catalog_is_rejected(tmp_path, mutate, match: str) -> None:
    groups = json.loads(GROUPS_FILE.read_text(encoding="utf-8"))
    mutate(groups)
    monkeypatch = _write_groups(tmp_path, groups)
    try:
        with pytest.raises(ValueError, match=match):
            load_place_groups()
    finally:
        monkeypatch.undo()
        load_place_groups.cache_clear()


def test_effective_group_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    group = effective_place_group(None, PlaceKindEnum.PLACE)
    assert group is not None
    assert group["key"] == DEFAULT_EMERGENT_GROUP
    assert group["clearable"] is True
    settlement = effective_place_group("settlement", PlaceKindEnum.PLACE)
    assert settlement is not None
    assert settlement["key"] == "settlement"
    assert effective_place_group(None, PlaceKindEnum.VAULT) is None
    assert effective_place_group("not_a_group", PlaceKindEnum.PLACE) is None
    # VAULT rows never inherit the default; the flag turns the fallback off.
    monkeypatch.setattr(game_config.features, "emergent_sites", False)
    assert effective_place_group(None, PlaceKindEnum.PLACE) is None
