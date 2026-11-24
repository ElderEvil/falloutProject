"""Pure duel resolver over frozen snapshots: no session, ORM, RNG or config access.

Every number used here is read from the snapshot, so replaying a stored journal
never depends on today's game_config or a dweller's live equipment.
"""

from dataclasses import dataclass
from operator import itemgetter
from typing import Any

from app.services.combat.incident_math import split_damage

CHALLENGER = "challenger"
DEFENDER = "defender"
_SIDE_RANK = {CHALLENGER: 0, DEFENDER: 1}
_KIND_RANK = {"hit": 0, "outcome": 1}


@dataclass(frozen=True)
class DuelResolution:
    outcome: str
    journal: list[dict[str, Any]]


def _member_damage(member: dict[str, Any], index: int, round_seq: int, level_bonus_damage: float) -> int:
    """Deterministic per-member swing inside its frozen range; no RNG is involved."""
    damage_min = int(member["damage_min"])
    damage_max = int(member["damage_max"])
    span = max(0, damage_max - damage_min)
    swing = (index * 7 + round_seq * 3) % (span + 1) if span else 0
    level_bonus = round(int(member["level_bonus"]) * level_bonus_damage)
    return damage_min + swing + level_bonus


def _side_damage(side: dict[str, Any], round_seq: int, level_bonus_damage: float) -> int:
    return sum(_member_damage(member, i, round_seq, level_bonus_damage) for i, member in enumerate(side["members"]))


def _side_power(side: dict[str, Any]) -> float:
    return float(sum(float(member["power"]) for member in side["members"]))


def _append_hits(
    journal: list[tuple[tuple[int, int, int, int], dict[str, Any]]],
    *,
    round_seq: int,
    attacker: str,
    members: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    damage: int,
) -> None:
    """Split one side's round damage across the opposing party, in fixed member order.

    Each line names one attacking dweller, rotating the roster by round and target index so the
    whole party speaks over a duel. The pick is a pure index, never RNG, so replays are exact.
    """
    for index, (target, share) in enumerate(zip(targets, split_damage(damage, len(targets)), strict=True)):
        actor = members[(round_seq - 1 + index) % len(members)]["name"]
        journal.append(
            (
                (round_seq, _KIND_RANK["hit"], _SIDE_RANK[attacker], index),
                {
                    "round_seq": round_seq,
                    "kind": "hit",
                    "side": attacker,
                    "damage": share,
                    "actor": actor,
                    "target": target["name"],
                    "message": f"{actor} hits {target['name']} for {share}.",
                },
            )
        )


def resolve_duel(challenger: dict[str, Any], defender: dict[str, Any]) -> DuelResolution:
    """Resolve a duel from two snapshots sharing one frozen tuning block.

    Tie rule: if both pools reach zero in the same round, the side with more power
    remaining at the start of that round wins; equal power means the challenger wins.
    """
    tuning = challenger["tuning"]
    if defender["tuning"] != tuning:
        raise ValueError("duel snapshots must share one tuning block")
    max_rounds = int(tuning["max_rounds"])
    hp_per_power = float(tuning["hp_per_power"])
    level_bonus_damage = float(tuning["level_bonus_damage"])

    challenger_pool = _side_power(challenger) * hp_per_power
    defender_pool = _side_power(defender) * hp_per_power
    entries: list[tuple[tuple[int, int, int, int], dict[str, Any]]] = []
    round_seq = 0
    while round_seq < max_rounds and challenger_pool > 0 and defender_pool > 0:
        round_seq += 1
        challenger_remaining, defender_remaining = challenger_pool, defender_pool
        challenger_damage = _side_damage(challenger, round_seq, level_bonus_damage)
        defender_damage = _side_damage(defender, round_seq, level_bonus_damage)
        _append_hits(
            entries,
            round_seq=round_seq,
            attacker=CHALLENGER,
            members=challenger["members"],
            targets=defender["members"],
            damage=challenger_damage,
        )
        _append_hits(
            entries,
            round_seq=round_seq,
            attacker=DEFENDER,
            members=defender["members"],
            targets=challenger["members"],
            damage=defender_damage,
        )
        challenger_pool -= defender_damage
        defender_pool -= challenger_damage

        challenger_down = challenger_pool <= 0
        defender_down = defender_pool <= 0
        if challenger_down and defender_down:
            winner = CHALLENGER if challenger_remaining >= defender_remaining else DEFENDER
        elif defender_down:
            winner = CHALLENGER
        elif challenger_down:
            winner = DEFENDER
        else:
            continue
        return _finish(entries, winner, challenger, defender, round_seq)

    # Round limit reached with both sides standing: more pool left wins, ties favour the challenger.
    winner = CHALLENGER if challenger_pool >= defender_pool else DEFENDER
    return _finish(entries, winner, challenger, defender, round_seq)


def _finish(
    entries: list[tuple[tuple[int, int, int, int], dict[str, Any]]],
    winner: str,
    challenger: dict[str, Any],
    defender: dict[str, Any],
    round_seq: int,
) -> DuelResolution:
    loser = DEFENDER if winner == CHALLENGER else CHALLENGER
    entries.append(
        (
            (round_seq, _KIND_RANK["outcome"], _SIDE_RANK[winner], 0),
            {
                "round_seq": round_seq,
                "kind": "outcome",
                "side": winner,
                "damage": 0,
                "actor": (challenger if winner == CHALLENGER else defender)["vault_name"],
                "target": (challenger if loser == CHALLENGER else defender)["vault_name"],
                "message": f"{(challenger if winner == CHALLENGER else defender)['vault_name']} wins.",
            },
        )
    )
    entries.sort(key=itemgetter(0))
    return DuelResolution(outcome=winner, journal=[entry for _, entry in entries])
