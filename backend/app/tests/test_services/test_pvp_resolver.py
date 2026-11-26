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
    assert first.journal == second.journal
    assert json.dumps(first.journal) == json.dumps(second.journal)
    assert _hash(first.journal) == _hash(second.journal)


def test_hit_lines_name_dwellers_and_the_outcome_stays_vault_level() -> None:
    challenger = _side("Alpha", [_member("Ada", 20, 12), _member("Bo", 15, 9)])
    defender = _side("Beta", [_member("Cy", 18, 11), _member("Dee", 14, 8)])

    journal = resolve_duel(challenger, defender).journal

    assert [entry["message"] for entry in journal] == [
        "Ada hits Cy for 11.",
        "Bo hits Dee for 10.",
        "Cy hits Ada for 10.",
        "Dee hits Bo for 9.",
        "Bo hits Cy for 11.",
        "Ada hits Dee for 10.",
        "Dee hits Ada for 10.",
        "Cy hits Bo for 9.",
        "Alpha wins.",
    ]
    assert [entry["round_seq"] for entry in journal] == sorted(entry["round_seq"] for entry in journal)
    assert journal[-1] == {
        "round_seq": 2,
        "kind": "outcome",
        "side": CHALLENGER,
        "damage": 0,
        "actor": "Alpha",
        "target": "Beta",
        "message": "Alpha wins.",
    }
    # Journal order is round -> side -> target; hit actors come from the attacking side.
    hits = [entry for entry in journal if entry["kind"] == "hit"]
    order = [(entry["round_seq"], 0 if entry["side"] == CHALLENGER else 1) for entry in hits]
    assert order == sorted(order)
    assert [entry["target"] for entry in hits if entry["round_seq"] == 1 and entry["side"] == CHALLENGER] == [
        "Cy",
        "Dee",
    ]
    challenger_names = {member["name"] for member in challenger["members"]}
    defender_names = {member["name"] for member in defender["members"]}
    for entry in hits:
        actor, _, rest = entry["message"].partition(" hits ")
        assert actor == entry["actor"]
        assert rest.startswith(f"{entry['target']} for ")
        attackers, defenders = (
            (challenger_names, defender_names)
            if entry["side"] == CHALLENGER
            else (
                defender_names,
                challenger_names,
            )
        )
        assert actor in attackers
        assert entry["target"] in defenders


def test_hit_lines_rotate_the_roster_across_rounds_and_targets() -> None:
    challenger = _side("Alpha", [_member("Ada", 30, 12), _member("Bo", 25, 9), _member("Cal", 20, 7)])
    defender = _side("Beta", [_member("Cy", 40, 10), _member("Dee", 35, 8)])
    names = [member["name"] for member in challenger["members"]]

    hits = [entry for entry in resolve_duel(challenger, defender).journal if entry["kind"] == "hit"]
    actors_by_round: dict[int, list[str]] = {}
    for entry in hits:
        if entry["side"] == CHALLENGER:
            actors_by_round.setdefault(entry["round_seq"], []).append(entry["actor"])

    assert len(actors_by_round) == 3
    for round_seq, actors in actors_by_round.items():
        assert actors == [names[(round_seq - 1 + index) % len(names)] for index in range(len(actors))]
    assert [actors[0] for actors in actors_by_round.values()] == ["Ada", "Bo", "Cal"]


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
