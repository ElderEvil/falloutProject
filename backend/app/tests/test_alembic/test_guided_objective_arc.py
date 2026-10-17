"""Guided objective content and migration preserve existing player progress."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink


async def test_guided_arc_migration_is_idempotent_and_preserves_claimed_rewards(async_session, vault):
    path = Path(__file__).parents[2] / "alembic/versions/2026_10_13_0001-b7d93840ac12_extend_guided_objective_arc.py"
    spec = importlib.util.spec_from_file_location("guided_arc_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert len(migration._STEPS) == 4
    old = Objective(challenge="Office already built", reward="200 caps", category="starter", sequence=7)
    old_link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=old.id, progress=1, total=1, is_completed=True
    )
    async_session.add_all([old, old_link])
    await async_session.commit()

    async def apply():
        def run(session):
            with patch.object(migration.op, "get_bind", return_value=session.connection()):
                migration.upgrade()

        await async_session.run_sync(run)

    await apply()
    await apply()
    await async_session.refresh(old_link)
    assert old_link.is_completed is True
    links = (
        (
            await async_session.execute(
                select(VaultObjectiveProgressLink).where(VaultObjectiveProgressLink.vault_id == vault.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(links) == 5
    assert all(not link.is_completed and link.progress == 0 for link in links if link.objective_id != old.id)


@pytest.mark.parametrize(
    "template_key", ["starter:reverse-engineer a schematic", "starter:reverse-engineer a schematic#v2"]
)
@pytest.mark.parametrize("claimed", [False, True])
async def test_scrap_guidance_migration_preserves_earned_and_claimed_rewards(
    async_session, vault, template_key, claimed
):
    path = (
        Path(__file__).parents[2] / "alembic/versions/2026_10_16_0003-d8e4c7a2b915_clarify_starter_scrap_objective.py"
    )
    spec = importlib.util.spec_from_file_location("scrap_guidance_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    objective = Objective(
        challenge="Reverse-engineer a schematic",
        description="Scrap it to learn its schematic.",
        reward="300 caps",
        category="starter",
        objective_type="scrap",
        template_key=template_key,
        target_entity={"item_type": "weapon", "rarity": "rare"},
        sequence=6,
    )
    link = VaultObjectiveProgressLink(
        vault_id=vault.id,
        objective_id=objective.id,
        progress=1,
        total=1,
        is_completed=claimed,
        reward_snapshot="300 caps",
    )
    async_session.add_all([objective, link])
    await async_session.commit()

    def apply(session):
        with patch.object(migration.op, "get_bind", return_value=session.connection()):
            migration.upgrade()
            migration.upgrade()

    await async_session.run_sync(apply)
    await async_session.refresh(objective)
    await async_session.refresh(link)
    starter_path = Path(__file__).parents[2] / "data/objectives/starter.json"
    seed = next(row for row in json.loads(starter_path.read_text()) if row["objective_type"] == "scrap")
    assert objective.challenge == seed["challenge"] == "Scrap a rare weapon"
    assert objective.description == seed["description"]
    assert objective.template_key == template_key
    assert objective.target_entity == {"item_type": "weapon", "rarity": "rare"}
    assert objective.reward == link.reward_snapshot == "300 caps"
    assert (link.progress, link.total, link.is_completed) == (1, 1, claimed)
