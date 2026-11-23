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
    scratch = tmp_path / "place_loot.json"
    scratch.write_text(json.dumps(data), encoding="utf-8")
    load_place_loot.cache_clear()
    loot_table.cache_clear()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("app.utils.place_loot.LOOT_FILE", scratch)
    return monkeypatch


MUTATIONS = [
    (lambda d: d["tables"]["low"]["items"][0].update(type="medicine"), "unknown type"),
    (lambda d: d["tables"]["low"]["items"][0].update(rarity="epic"), "unknown rarity"),
    (lambda d: d["tables"]["automotive"]["items"][0].update(junk_types=["unobtainium"]), "unknown values"),
    (lambda d: d["tables"]["automotive"]["items"][2].update(weapon_types=["gun"]), "only applies to weapon entries"),
    (lambda d: d["tables"]["automotive"]["items"][0].update(junk_types=[]), "non-empty list"),
    (lambda d: d["tables"]["low"].update(caps={"min": 50, "max": 10}), r"0 <= min <= max"),
    (lambda d: d["tables"]["low"].update(caps={"min": True, "max": 10}), "integer caps"),
    (lambda d: d.clear() or d.update(tables={}), "non-empty 'tables'"),
]


@pytest.mark.parametrize(("mutate", "match"), MUTATIONS)
def test_bad_loot_catalog_is_rejected(tmp_path, mutate, match: str) -> None:
    data = json.loads(LOOT_FILE.read_text(encoding="utf-8"))
    mutate(data)
    monkeypatch = _write_loot(tmp_path, data)
    try:
        with pytest.raises(ValueError, match=match):
            load_place_loot()
    finally:
        monkeypatch.undo()
        load_place_loot.cache_clear()
