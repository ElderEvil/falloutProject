"""Resolver contract: determinism, journal ordering and the simultaneous-defeat tie rule."""

import hashlib
import json
from typing import Any

import pytest

from app.services.pvp.resolver import CHALLENGER, DEFENDER, resolve_duel

TUNING: dict[str, Any] = {"max_rounds": 5, "hp_per_power": 1.0, "level_bonus_damage": 0.0}


def _side(name: str, members: list[dict[str, Any]]) -> dict[str, Any]:
    return {"vault_id": name, "vault_name": name, "tuning": TUNING, "members": members, "party_size": len(members)}


def _member(name: str, power: float, damage: int, level_bonus: int = 0) -> dict[str, Any]:
    return {
        "dweller_id": name,
        "name": name,
        "power": power,
        "damage_min": damage,
        "damage_max": damage,
        "level_bonus": level_bonus,
    }


def _hash(journal: list[dict[str, Any]]) -> str:
    return hashlib.sha256(json.dumps(journal, sort_keys=True).encode()).hexdigest()


def test_identical_snapshots_produce_a_byte_identical_journal() -> None:
    challenger = _side("Alpha", [_member("Ada", 20, 12), _member("Bo", 15, 9)])
    defender = _side("Beta", [_member("Cy", 18, 11), _member("Dee", 14, 8)])

    first = resolve_duel(challenger, defender)
    second = resolve_duel(challenger, defender)

    assert first.outcome == second.outcome
    assert _hash(first.journal) == _hash(second.journal)


def test_journal_order_is_round_then_side_then_target() -> None:
    challenger = _side("Alpha", [_member("Ada", 20, 12), _member("Bo", 15, 9)])
    defender = _side("Beta", [_member("Cy", 18, 11), _member("Dee", 14, 8)])

    journal = resolve_duel(challenger, defender).journal

    hits = [entry for entry in journal if entry["kind"] == "hit"]
    order = [(entry["round_seq"], 0 if entry["side"] == CHALLENGER else 1) for entry in hits]
    assert order == sorted(order)
    first_round_targets = [entry["target"] for entry in hits if entry["round_seq"] == 1 and entry["side"] == CHALLENGER]
    assert first_round_targets == ["Cy", "Dee"]
    assert journal[-1]["kind"] == "outcome"
    assert [entry["round_seq"] for entry in journal] == sorted(entry["round_seq"] for entry in journal)


def test_simultaneous_defeat_goes_to_the_side_with_more_power_left() -> None:
    # Both pools empty in round one; the defender started with more power remaining.
    challenger = _side("Alpha", [_member("Ada", 10, 12)])
    defender = _side("Beta", [_member("Cy", 12, 10)])

    resolution = resolve_duel(challenger, defender)

    assert resolution.outcome == DEFENDER
    assert resolution.journal[-1]["side"] == DEFENDER


def test_simultaneous_defeat_with_equal_power_goes_to_the_challenger() -> None:
    challenger = _side("Alpha", [_member("Ada", 10, 10)])
    defender = _side("Beta", [_member("Cy", 10, 10)])

    resolution = resolve_duel(challenger, defender)

    assert resolution.outcome == CHALLENGER


def test_snapshots_must_share_tuning() -> None:
    challenger = _side("Alpha", [_member("Ada", 10, 10)])
    defender = _side("Beta", [_member("Cy", 10, 10)])
    defender["tuning"] = {**TUNING, "hp_per_power": 3.0}

    with pytest.raises(ValueError, match="tuning"):
        resolve_duel(challenger, defender)
