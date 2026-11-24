"""Snapshot freezing: a replay must not move when game_config or equipment changes."""

import hashlib
import json

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud.dweller import dweller as dweller_crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.services.pvp.resolver import resolve_duel
from app.services.pvp.snapshots import POWER_BANDS, build_snapshot, power_band


def _hash(journal: list[dict]) -> str:
    return hashlib.sha256(json.dumps(journal, sort_keys=True).encode()).hexdigest()


def _opponent(snapshot: dict) -> dict:
    return {
        "vault_id": "rival",
        "vault_name": "Rival",
        "party_size": 1,
        "power_band": "steady",
        "members": [
            {
                "dweller_id": "rival-1",
                "name": "Rival",
                "power": 50.0,
                "damage_min": 20,
                "damage_max": 30,
                "level_bonus": 4,
            }
        ],
        "tuning": snapshot["tuning"],
    }


@pytest.mark.asyncio
async def test_snapshot_freezes_power_and_level_bonus(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch: pytest.MonkeyPatch
) -> None:
    loaded = await dweller_crud.get(async_session, dweller.id)
    snapshot = build_snapshot(vault, [loaded])
    expected_level_bonus = dweller.level * game_config.combat.level_bonus_multiplier
    before = resolve_duel(snapshot, _opponent(snapshot))

    monkeypatch.setattr(game_config.combat, "level_bonus_multiplier", 9)
    monkeypatch.setattr(
        game_config.combat,
        "weapon_stat_weights",
        {
            "unarmed": {"strength": 1.0},
            "melee": {"strength": 1.0},
            "gun": {"perception": 1.0},
            "energy": {"intelligence": 1.0},
            "heavy": {"endurance": 1.0},
        },
    )
    after = resolve_duel(snapshot, _opponent(snapshot))
    rebuilt = build_snapshot(vault, [loaded])

    assert _hash(before.journal) == _hash(after.journal)
    assert before.outcome == after.outcome
    assert rebuilt["members"][0]["level_bonus"] != snapshot["members"][0]["level_bonus"]
    assert snapshot["members"][0]["level_bonus"] == expected_level_bonus


def test_power_band_is_coarse() -> None:
    assert {band for _, band in POWER_BANDS} <= {"light", "steady", "strong", "elite"}
    assert power_band(0) == "light"
    assert power_band(74) == "light"
    assert power_band(75) == "steady"
    assert power_band(174) == "steady"
    assert power_band(175) == "strong"
    assert power_band(299) == "strong"
    assert power_band(300) == "elite"
    # The top band must be reachable by a legal party: 3 x 134 (Lv50, SPECIAL 10, best weapon).
    assert power_band(402) == "elite"
