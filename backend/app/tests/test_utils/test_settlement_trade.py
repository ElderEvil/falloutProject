"""Caravan shipment catalog (issue 1493): content rules, not behavior."""

import json

import pytest

from app.core.enums import JunkTypeEnum
from app.core.game_config import game_config
from app.utils.place_groups import (
    TRADE_FILE,
    TRADE_GROUPS,
    get_place_group,
    group_for_place_name,
    load_settlement_trade,
    seeded_place_groups,
    trade_caps_cost,
    trade_entry,
    trade_tier,
)


def _entries() -> list[dict]:
    return json.loads(TRADE_FILE.read_text(encoding="utf-8"))["places"]


def _write(tmp_path, entries: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    scratch = tmp_path / "settlement_trade.json"
    scratch.write_text(json.dumps({"places": entries}), encoding="utf-8")
    load_settlement_trade.cache_clear()
    monkeypatch.setattr("app.utils.place_groups.TRADE_FILE", scratch)


def test_every_tradeable_place_has_one_shipment() -> None:
    trade = load_settlement_trade()
    tradeable = {name for name, group in seeded_place_groups().items() if group in TRADE_GROUPS}

    assert set(trade) == tradeable
    assert len({entry["place"] for entry in trade.values()}) == len(trade)


def test_shipments_are_common_material_with_a_clearable_benchmark() -> None:
    junk = {member.value for member in JunkTypeEnum}

    for entry in _entries():
        assert entry["material"] in junk
        low, high = entry["band"]
        assert 1 <= low <= high <= 10
        benchmark = get_place_group(group_for_place_name(entry["comparable"]))
        assert benchmark is not None, entry["comparable"]
        assert benchmark["clearable"] is True, entry["comparable"]


def test_every_material_is_reachable_somewhere() -> None:
    """A material nobody ships cannot be the reason a player picks a settlement."""
    shipped = {entry["material"] for entry in _entries()}
    assert shipped == {member.value for member in JunkTypeEnum}


def test_trade_lookup_is_by_place_name_and_silent_when_untradeable() -> None:
    megaton = trade_entry("Megaton")
    assert megaton is not None
    assert megaton["material"] == "steel"
    assert trade_entry("megaton") is not None
    assert trade_entry("Concord") is None  # a clearable ruin, never a caravan destination
    assert trade_entry("Vault 101") is None


def test_tiers_fees_and_untradeable_groups() -> None:
    settlement = get_place_group("settlement")
    city = get_place_group("city")

    assert trade_tier(settlement) == 1
    assert trade_tier(city) == 2
    assert trade_tier(get_place_group("factory")) == 0
    assert trade_caps_cost(settlement) == game_config.exploration.caravan.caps_cost_settlement
    assert trade_caps_cost(city) == game_config.exploration.caravan.caps_cost_city
    assert trade_caps_cost(get_place_group("factory")) == 0


def test_a_material_without_a_common_item_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A shipment must name a material the resolver can actually ship, not just a valid enum value."""
    from types import SimpleNamespace

    from app.utils import place_groups
    from app.utils.static_data import game_data_store

    without_common = [item for item in game_data_store.junk_items if str(item.rarity).lower() != "common"]
    monkeypatch.setattr("app.utils.static_data.game_data_store", SimpleNamespace(junk_items=without_common))
    place_groups.load_settlement_trade.cache_clear()
    try:
        with pytest.raises(ValueError, match="no common junk item"):
            place_groups.load_settlement_trade()
    finally:
        place_groups.load_settlement_trade.cache_clear()


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda entries: entries[0].update(material="gold"), "known junk material"),
        (lambda entries: entries[0].update(band=[0, 2]), "integer band"),
        (lambda entries: entries[0].update(band=[3, 2]), "integer band"),
        (lambda entries: entries[0].update(comparable="Diamond City"), "clearable comparable site"),
        (lambda entries: entries[0].update(place="Concord"), "settlement or city seed place"),
        (lambda entries: entries.append(dict(entries[0])), "Duplicate caravan shipment"),
        (lambda entries: entries.pop(), "without a caravan shipment"),
    ],
)
def test_invalid_catalog_is_rejected(tmp_path, mutate, match: str, monkeypatch: pytest.MonkeyPatch) -> None:
    entries = _entries()
    mutate(entries)
    _write(tmp_path, entries, monkeypatch)
    try:
        with pytest.raises(ValueError, match=match):
            load_settlement_trade()
    finally:
        monkeypatch.undo()
        load_settlement_trade.cache_clear()
