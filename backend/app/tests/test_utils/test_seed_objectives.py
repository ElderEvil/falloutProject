import json
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.crud.objective import objective_crud
from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.services import catalog_service as data_loader
from app.utils.objective_constants import (
    VALID_REACH_TYPES,
    VALID_RESOURCE_TYPES,
    VALID_ROOM_TYPES,
    normalize_resource_type,
    normalize_room_type,
)
from app.utils.seed_objectives import seed_objectives_from_json
from app.utils.static_data import DATA_DIR


def _dir(tmp_path: Path, name: str = "objectives") -> Path:
    path = tmp_path / name
    path.mkdir()
    return path


def _put(directory: Path, name: str, payload) -> None:
    (directory / name).write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")


def _objective(challenge: str, reward: str, **extra) -> dict:
    return {"challenge": challenge, "reward": reward, "category": "achievement"} | extra


SEED_CASES = [
    ({}, 0, 0, []),
    ({"single.json": _objective("Single objective", "1 lunchbox")}, 1, 1, ["Single objective"]),
    (
        {"invalid.json": "{ invalid json }", "valid.json": [_objective("Valid objective", "10 caps")]},
        1,
        1,
        ["Valid objective"],
    ),
    ({"mixed.json": [{"challenge": "Missing reward field"}, _objective("Valid objective", "50 caps")]}, 0, 0, []),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("files", "seeded", "total", "present"), SEED_CASES)
async def test_seed_objectives_counts_and_validates_files(
    async_session: AsyncSession, tmp_path: Path, files: dict, seeded: int, total: int, present: list
):
    objectives_dir = _dir(tmp_path)
    for name, payload in files.items():
        _put(objectives_dir, name, payload)
    assert await seed_objectives_from_json(async_session, objectives_dir=objectives_dir) == seeded
    result = await async_session.execute(select(Objective))
    objectives = result.scalars().all()
    assert len(objectives) == total
    assert {objective.challenge for objective in objectives} == set(present)


@pytest.mark.asyncio
async def test_seed_objectives_prevents_duplicates(async_session: AsyncSession, tmp_path: Path) -> None:
    objectives_dir = _dir(tmp_path)
    _put(objectives_dir, "assign.json", [_objective("Assign 2 dwellers", "25 caps")])
    assert await seed_objectives_from_json(async_session, objectives_dir=objectives_dir) == 1
    assert await seed_objectives_from_json(async_session, objectives_dir=objectives_dir) == 0
    assert len((await async_session.execute(select(Objective))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_seed_objectives_rollback_on_error(async_session: AsyncSession, tmp_path: Path) -> None:
    objectives_dir = _dir(tmp_path)
    _put(objectives_dir, "test.json", [_objective("Test objective", "10 caps")])
    with patch.object(async_session, "commit", side_effect=Exception("Database error")):
        assert await seed_objectives_from_json(async_session, objectives_dir=objectives_dir) == 0
    assert len((await async_session.execute(select(Objective))).scalars().all()) == 0


@pytest.mark.asyncio
async def test_get_multi_complete_returns_only_complete_objectives(async_session: AsyncSession, tmp_path: Path) -> None:
    objectives_dir = _dir(tmp_path)
    food, wildcard = {"resource_type": "food"}, {"room_type": "*"}
    _put(
        objectives_dir,
        "mixed.json",
        [
            _objective("Collect 100 food", "50 caps", objective_type="collect", target_entity=food, target_amount=100),
            _objective("Incomplete 1", "10 caps"),
            _objective("Assign 5 dwellers", "150 caps", objective_type="assign", target_amount=5),
            _objective("Build 1 Room", "100 caps", objective_type="build", target_entity=wildcard, target_amount=1),
            _objective("Build 3 Rooms", "1000 caps", objective_type="build", target_entity=wildcard, target_amount=3),
        ],
    )
    assert await seed_objectives_from_json(async_session, objectives_dir=objectives_dir) == 5

    complete_objectives = await objective_crud.get_multi_complete(async_session, skip=0, limit=10)
    assert len(complete_objectives) == 3, (
        f"Expected 3, got {len(complete_objectives)}: {[o.challenge for o in complete_objectives]}"
    )
    challenges = {obj.challenge for obj in complete_objectives}
    assert challenges == {"Collect 100 food", "Assign 5 dwellers", "Build 3 Rooms"}
    for obj in complete_objectives:
        assert obj.objective_type is not None
        assert obj.target_amount > 1


def test_starter_seed_file_integrity() -> None:
    starter_file = DATA_DIR / "objectives" / "starter.json"
    assert starter_file.exists(), "starter.json must exist"
    steps = json.loads(starter_file.read_text(encoding="utf-8"))
    assert len(steps) > 11
    supported_types = {
        "assign",
        "build",
        "collect",
        "reach",
        "assign_correct",
        "scrap",
        "train",
        "expedition",
        "explore",
        "equip",
    }
    sequences = []
    for step in steps:
        assert step["category"] == "starter"
        assert step["objective_type"] in supported_types, f"unsupported type {step['objective_type']}"
        assert step["objective_type"] != "kill"
        assert 3 <= len(step["challenge"]) <= 32
        assert 3 <= len(step["reward"]) <= 32
        assert step.get("description"), "description required"
        sequences.append(step["sequence"])
        target = step.get("target_entity") or {}
        if step["objective_type"] == "build":
            assert normalize_room_type(target.get("room_type")) in VALID_ROOM_TYPES
        elif step["objective_type"] == "collect":
            resource = target.get("resource_type")
            if resource:
                assert normalize_resource_type(resource) in VALID_RESOURCE_TYPES
        elif step["objective_type"] == "reach":
            assert target.get("reach_type") in VALID_REACH_TYPES

    assert sequences == list(range(len(steps))), "fresh-cohort positions are unique and contiguous"
    assert all(step["template_key"].endswith("#v3") for step in steps)
    catalog = {
        "weapon": {str(w["name"]).lower() for w in data_loader.load_weapons()},
        "outfit": {str(o["name"]).lower() for o in data_loader.load_outfits()},
    }
    for path in (DATA_DIR / "objectives").glob("*.json"):
        for entry in json.loads(path.read_text()):
            prefix, sep, name = str(entry.get("reward", "")).partition(":")
            if sep and prefix.lower() in catalog:
                name = name.rsplit(":", 1)[-1]
                assert name.strip().lower() in catalog[prefix.lower()], f"{path.name}: {entry['reward']}"


def _legacy_objective(**overrides) -> Objective:
    base = {
        "template_key": "starter:legacy",
        "challenge": "Legacy task",
        "reward": "50 caps",
        "category": "starter",
        "objective_type": "collect",
        "target_entity": {"resource_type": "food"},
        "target_amount": 50,
        "sequence": 2,
    }
    return Objective(**(base | overrides))


async def test_starter_balance_refreshes_existing_templates_without_progress_backfill(async_session, tmp_path, vault):
    path = tmp_path / "starter.json"
    template = {
        "challenge": "Teach production",
        "template_key": "starter:teach production",
        "category": "starter",
        "reward": "50 caps",
        "objective_type": "collect",
        "target_entity": {"resource_type": "power", "production_only": True},
        "target_amount": 50,
        "sequence": 0,
    }
    path.write_text(json.dumps([template]))
    assert await seed_objectives_from_json(async_session, tmp_path) == 1
    original = (await objective_crud.get_by_category(async_session, "starter"))[0]
    # Earlier releases left an inactive canonical row and an active #v2 copy.
    original.assignable = False
    previous_release = Objective(**template | {"template_key": template["template_key"] + "#v2"})
    async_session.add_all([original, previous_release])
    await async_session.commit()
    path.write_text(json.dumps([template | {"reward": "dweller:Mechanic", "sequence": 1}]))
    assert await seed_objectives_from_json(async_session, tmp_path) == 0
    rows = await objective_crud.get_by_category(async_session, "starter")
    updated = next(row for row in rows if row.id == original.id)
    assert updated.id == original.id
    assert updated.reward == "dweller:Mechanic"
    assert updated.sequence == 1
    assert updated.assignable
    await async_session.refresh(previous_release)
    assert not previous_release.assignable
    assert await objective_crud.assign_initial(async_session, vault.id, is_boosted=False) == 1
    assigned = await objective_crud.get_multi_for_vault(async_session, vault.id)
    assert [row.reward for row in assigned] == ["dweller:Mechanic"]


async def test_versioned_starter_switch_preserves_assigned_legacy_contract(async_session, tmp_path, vault):
    old = _legacy_objective()
    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=old.id, progress=17, total=50, reward_snapshot="50 caps"
    )
    async_session.add_all([old, link])
    await async_session.commit()
    revised = {
        "template_key": "starter:legacy#v3",
        "challenge": "Revised task",
        "reward": "dweller:Theo Mercer",
        "category": "starter",
        "objective_type": "collect",
        "target_entity": {"resource_type": "food"},
        "target_amount": 100,
        "sequence": 5,
        "description": "Keep the diner producing.",
    }
    (tmp_path / "starter.json").write_text(json.dumps([revised]))
    assert await seed_objectives_from_json(async_session, tmp_path) == 1
    await async_session.refresh(old)
    await async_session.refresh(link)
    assert not old.assignable
    assert (old.challenge, old.reward, old.sequence, old.target_amount) == ("Legacy task", "50 caps", 2, 50)
    assert (link.progress, link.total, link.reward_snapshot, link.is_completed) == (17, 50, "50 caps", False)
    assert await objective_crud.get_current_starter_id(async_session, vault.id) == old.id
    assigned = await objective_crud.get_multi_for_vault(async_session, vault.id)
    assert [(o.id, o.reward) for o in assigned] == [(old.id, "50 caps")]
    active = [o for o in await objective_crud.get_by_category(async_session, "starter") if o.assignable]
    assert [o.template_key for o in active] == ["starter:legacy#v3"]


async def test_starter_activation_failure_keeps_old_cohort_and_retry_is_idempotent(async_session, tmp_path, vault):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    old = _legacy_objective(sequence=0)
    async_session.add(old)
    await async_session.commit()
    revised = {
        "template_key": "starter:replacement#v3",
        "challenge": "Replacement task",
        "reward": "50 caps",
        "category": "starter",
        "objective_type": "collect",
        "target_entity": {"resource_type": "food"},
        "target_amount": 100,
        "sequence": 0,
    }
    (tmp_path / "starter.json").write_text(json.dumps([revised]))
    await async_session.execute(
        text("""
        CREATE TRIGGER reject_starter_activation BEFORE UPDATE ON objective
        WHEN NEW.template_key = 'starter:replacement#v3' AND NEW.assignable = 1
        BEGIN SELECT RAISE(ABORT, 'late activation failure'); END
    """)
    )
    await async_session.commit()
    with pytest.raises(IntegrityError, match="late activation failure"):
        await seed_objectives_from_json(async_session, tmp_path)
    await async_session.rollback()
    await async_session.refresh(old)
    rows = await objective_crud.get_by_category(async_session, "starter")
    replacement = next(o for o in rows if o.template_key == "starter:replacement#v3")
    assert old.assignable
    assert not replacement.assignable
    replacement_id = replacement.id
    await async_session.execute(text("DROP TRIGGER reject_starter_activation"))
    await async_session.commit()
    assert await seed_objectives_from_json(async_session, tmp_path) == 0
    await async_session.refresh(old)
    await async_session.refresh(replacement)
    assert not old.assignable
    assert replacement.assignable
    assert replacement.id == replacement_id
    assert len(await objective_crud.get_by_category(async_session, "starter")) == 2
