"""Tests for the place-loot table catalog."""

import json

import pytest

from app.utils.place_groups import load_place_groups
from app.utils.place_loot import LOOT_FILE, load_place_loot, loot_table


def test_catalog_has_all_three_risk_tables() -> None:
    """The catalog ships low/medium/high tables with caps and item pools."""
    tables = load_place_loot()["tables"]
    assert set(tables) == {"low", "medium", "high"}
    for table in tables.values():
        assert 0 <= table["caps"]["min"] <= table["caps"]["max"]
        assert table["items"]


def test_every_clearable_group_loot_table_resolves() -> None:
    """Every clearable group points at a table that exists in the catalog."""
    tables = load_place_loot()["tables"]
    for group in load_place_groups():
        if group["clearable"]:
            assert group["loot_table"] in tables


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
    """A bool is an int in Python, but a boolean cap is an authoring error, not 1/0."""
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
