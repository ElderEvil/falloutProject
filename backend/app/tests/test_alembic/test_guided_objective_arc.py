"""Guided objective content and migration preserve existing player progress."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select

from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink


async def test_guided_arc_migration_is_idempotent_and_preserves_claimed_rewards(async_session, vault):
    path = Path(__file__).parents[2] / "alembic/versions/2026_10_10_0001-c34b7e019a62_extend_guided_objective_arc.py"
    spec = importlib.util.spec_from_file_location("guided_arc_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    seed = json.loads((Path(__file__).parents[2] / "data/objectives/starter.json").read_text())
    assert seed[-4:] == migration._STEPS
    assert [step["sequence"] for step in seed] == list(range(13))
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
