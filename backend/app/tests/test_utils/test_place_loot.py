import json

import pytest

from app.services.exploration.loot_calculator import loot_calculator
from app.utils.place_groups import load_place_groups
from app.utils.place_loot import LOOT_FILE, load_place_loot, loot_table


def test_catalog_keeps_the_risk_tables_and_adds_themed_tables() -> None:
    tables = load_place_loot()["tables"]
    assert {"low", "medium", "high"} <= set(tables)
    assert {"automotive", "household", "tech", "medical", "military"} <= set(tables)
    for table in tables.values():
        assert 0 <= table["caps"]["min"] <= table["caps"]["max"]
        assert table["items"]


def test_every_clearable_group_loot_table_resolves() -> None:
    tables = load_place_loot()["tables"]
    for group in load_place_groups():
        if group["clearable"]:
            assert group["loot_table"] in tables


def test_every_loot_entry_resolves_to_a_real_catalog_item() -> None:
    for table_key, table in load_place_loot()["tables"].items():
        for entry in table["items"]:
            item = loot_calculator.roll_item(
                5,
                entry["type"],
                entry["rarity"],
                junk_types=entry.get("junk_types"),
                weapon_types=entry.get("weapon_types"),
            )
            assert item.name, f"{table_key} entry rolled no item"


def test_each_themed_table_starts_with_a_single_category_signature() -> None:
    tables = load_place_loot()["tables"]
    for key in ("automotive", "household", "tech", "medical"):
        assert len(tables[key]["items"][0]["junk_types"]) == 1
    assert tables["military"]["items"][0]["weapon_types"] == ["gun", "heavy"]


def test_loot_table_returns_none_for_unknown_key() -> None:
    assert loot_table("low") is not None
    assert loot_table("not_a_table") is None


def _write_loot(tmp_path, data: dict) -> pytest.MonkeyPatch:
    """Point the loader at a scratch catalog and reset its cache."""
    scratch = tmp_path / "place_loot.json"
    scratch.write_text(json.dumps(data), encoding="utf-8")
    load_place_loot.cache_clear()
    loot_table.cache_clear()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("app.utils.place_loot.LOOT_FILE", scratch)
    return monkeypatch


def test_bad_item_type_is_rejected(tmp_path) -> None:
    data = json.loads(LOOT_FILE.read_text(encoding="utf-8"))
    data["tables"]["low"]["items"][0]["type"] = "medicine"
    monkeypatch = _write_loot(tmp_path, data)
    try:
        with pytest.raises(ValueError, match="unknown type"):
            load_place_loot()
    finally:
        monkeypatch.undo()
        load_place_loot.cache_clear()


def test_bad_item_rarity_is_rejected(tmp_path) -> None:
    data = json.loads(LOOT_FILE.read_text(encoding="utf-8"))
    data["tables"]["low"]["items"][0]["rarity"] = "epic"
    monkeypatch = _write_loot(tmp_path, data)
    try:
        with pytest.raises(ValueError, match="unknown rarity"):
            load_place_loot()
    finally:
        monkeypatch.undo()
        load_place_loot.cache_clear()


def test_unknown_junk_type_filter_is_rejected(tmp_path) -> None:
    data = json.loads(LOOT_FILE.read_text(encoding="utf-8"))
    data["tables"]["automotive"]["items"][0]["junk_types"] = ["unobtainium"]
    monkeypatch = _write_loot(tmp_path, data)
    try:
        with pytest.raises(ValueError, match="unknown values"):
            load_place_loot()
    finally:
        monkeypatch.undo()
        load_place_loot.cache_clear()


def test_category_filter_on_the_wrong_item_type_is_rejected(tmp_path) -> None:
    data = json.loads(LOOT_FILE.read_text(encoding="utf-8"))
    data["tables"]["automotive"]["items"][2]["weapon_types"] = ["gun"]
    monkeypatch = _write_loot(tmp_path, data)
    try:
        with pytest.raises(ValueError, match="only applies to weapon entries"):
            load_place_loot()
    finally:
        monkeypatch.undo()
        load_place_loot.cache_clear()


def test_empty_category_filter_is_rejected(tmp_path) -> None:
    data = json.loads(LOOT_FILE.read_text(encoding="utf-8"))
    data["tables"]["automotive"]["items"][0]["junk_types"] = []
    monkeypatch = _write_loot(tmp_path, data)
    try:
        with pytest.raises(ValueError, match="non-empty list"):
            load_place_loot()
    finally:
        monkeypatch.undo()
        load_place_loot.cache_clear()


def test_inverted_caps_range_is_rejected(tmp_path) -> None:
    data = json.loads(LOOT_FILE.read_text(encoding="utf-8"))
    data["tables"]["low"]["caps"] = {"min": 50, "max": 10}
    monkeypatch = _write_loot(tmp_path, data)
    try:
        with pytest.raises(ValueError, match="0 <= min <= max"):
            load_place_loot()
    finally:
        monkeypatch.undo()
        load_place_loot.cache_clear()


def test_boolean_cap_is_rejected(tmp_path) -> None:
    data = json.loads(LOOT_FILE.read_text(encoding="utf-8"))
    data["tables"]["low"]["caps"] = {"min": True, "max": 10}
    monkeypatch = _write_loot(tmp_path, data)
    try:
        with pytest.raises(ValueError, match="integer caps"):
            load_place_loot()
    finally:
        monkeypatch.undo()
        load_place_loot.cache_clear()


def test_empty_tables_object_is_rejected(tmp_path) -> None:
    monkeypatch = _write_loot(tmp_path, {"tables": {}})
    try:
        with pytest.raises(ValueError, match="non-empty 'tables'"):
            load_place_loot()
    finally:
        monkeypatch.undo()
        load_place_loot.cache_clear()
