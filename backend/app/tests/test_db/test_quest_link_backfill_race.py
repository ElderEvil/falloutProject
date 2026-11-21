"""PostgreSQL transaction boundaries for vault-quest link writers."""

import re
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import event, text
from sqlmodel import select

from app import crud
from app.core.enums import RewardType
from app.models.quest_reward import QuestReward
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.quest import QuestCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreate
from app.services.progression.quests.rotation import ensure_current_quest_rotation
from app.services.progression.quests.service import quest_service
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault

# The tests share one PostgreSQL database while xdist spreads them across workers;
# the session-level lock serializes them (the maker's single pooled connection keeps
# acquire and release on one backend).
_LOCK_SQL = text("SELECT pg_advisory_lock(hashtextextended(:lock_key, 0))")
_UNLOCK_SQL = text("SELECT pg_advisory_unlock(hashtextextended(:lock_key, 0))")
LOCK_KEY = "quest-link-lock-order-race"


async def _set_advisory_lock(maker, *, unlock: bool = False) -> None:
    async with maker() as session:
        await session.execute(_UNLOCK_SQL if unlock else _LOCK_SQL, {"lock_key": LOCK_KEY})


@pytest_asyncio.fixture(loop_scope="session")
async def quest_rows(pg_session_maker):
    engine, maker = pg_session_maker
    vault_id = user_id = None
    quest_ids = []
    await _set_advisory_lock(maker)
    try:
        async with maker() as setup:
            migrated = await setup.scalar(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_name = 'gamestate' "
                    "AND column_name IN ('daily_quests_period', 'weekly_quests_period')"
                )
            )
            if migrated != 2:
                pytest.skip("database schema predates the rotation migration; run alembic upgrade head")
            user = await crud.user.create(setup, obj_in=UserCreate(**create_fake_user()))
            user_id = user.id
            vault = await crud.vault.create_with_user_id(
                db_session=setup, obj_in=VaultCreate(**create_fake_vault()), user_id=user_id
            )
            vault_id = vault.id
            vault.bottle_caps = 1_000
            for label, quest_type in (("Side", "side"), ("Daily", "daily"), ("Weekly", "repeatable")):
                quest = await crud.quest_crud.create(
                    setup,
                    obj_in=QuestCreate(
                        title=label,
                        short_description="Lock-order fixture",
                        long_description="Lock the vault row before touching the link.",
                        requirements="No prerequisites",
                        rewards="10 caps",
                        quest_type=quest_type,
                    ),
                )
                quest_ids.append(quest.id)
            await setup.commit()
        yield engine, maker, vault_id, quest_ids[0], quest_ids[1]
    finally:
        try:
            async with maker() as cleanup:
                if vault_id is not None:
                    await cleanup.execute(
                        text("DELETE FROM vaultquestcompletionlink WHERE vault_id = :id"), {"id": vault_id}
                    )
                for quest_id in quest_ids:
                    await cleanup.execute(text("DELETE FROM quest WHERE id = :id"), {"id": quest_id})
                if vault_id is not None:
                    await cleanup.execute(text("DELETE FROM vault WHERE id = :id"), {"id": vault_id})
                if user_id is not None:
                    await cleanup.execute(text('DELETE FROM "user" WHERE id = :id'), {"id": user_id})
                await cleanup.commit()
        finally:
            await _set_advisory_lock(maker, unlock=True)


def _vault_lock_index(statements: list[tuple[str, bool, tuple[str, ...]]]) -> list[int]:
    return [i for i, (sql, locked, _bound) in enumerate(statements) if locked and re.search(r"FROM vault(?!\w)", sql)]


def _is_link_lock_or_write(sql: str, locked: bool) -> bool:
    """An unlocked link SELECT is a plain read, not a lock or write."""
    if locked and sql.startswith("SELECT vaultquestcompletionlink"):
        return True
    return sql.startswith(("INSERT INTO vaultquestcompletionlink", "UPDATE vaultquestcompletionlink"))


def _link_op_index(statements: list[tuple[str, bool, tuple[str, ...]]]) -> list[int]:
    return [i for i, (sql, locked, _bound) in enumerate(statements) if _is_link_lock_or_write(sql, locked)]


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.integration
async def test_arrival_noop_releases_the_link_lock(quest_rows) -> None:
    """A no-op arrival must end its transaction: a held link lock would deadlock the
    read path's vault-first rotation against a claim holding the vault lock."""
    _, maker, vault_id, side, _ = quest_rows
    async with maker() as arrange:
        arrange.add(
            VaultQuestCompletionLink(
                vault_id=vault_id,
                quest_id=side,
                is_visible=True,
                started_at=datetime.now(UTC),
                is_reward_ready=True,
            )
        )
        await arrange.commit()

    async with maker() as session:
        await quest_service.mark_quest_ready_to_claim(session, side, vault_id)
        assert not session.in_transaction(), "the no-op arrival must not keep the link lock"


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.integration
@pytest.mark.parametrize("case", ["claim", "assign_existing", "assign_missing", "list_backfill", "rotation"])
async def test_writer_locks_vault_before_link_ops(case: str, quest_rows) -> None:
    """Every quest-link writer locks the vault row before its first link lock or write.

    Observed on the SQL the writer actually emits, run sequentially: no scheduling
    to stage, no deadlocks to provoke, and a no-op cannot pass because the link
    operation itself is required. Arrangement happens before the listener window.
    """
    engine, maker, vault_id, side, daily = quest_rows
    async with maker() as arrange:
        if case == "claim":
            arrange.add(
                VaultQuestCompletionLink(vault_id=vault_id, quest_id=side, is_visible=True, is_reward_ready=True)
            )
            arrange.add(QuestReward(quest_id=side, reward_type=RewardType.CAPS, reward_data={"amount": 10}))
        elif case == "assign_existing":
            arrange.add(VaultQuestCompletionLink(vault_id=vault_id, quest_id=side, is_visible=False))
        await arrange.commit()

    async with maker() as session:
        statements: list[tuple[str, bool, tuple[str, ...]]] = []
        original_commit = session.commit

        async def recording_commit():
            await original_commit()
            # The commit lands after the statements it flushed, keeping the observed
            # stream in true execution order.
            statements.append(("__commit__", False, ()))

        session.commit = recording_commit

        def record(_conn, _cursor, statement, parameters, context, _executemany):
            original = getattr(getattr(context, "compiled", None), "statement", None)
            for_update = getattr(original, "_for_update_arg", None)
            locked = (
                for_update is not None
                and getattr(for_update, "read", False) is not True
                and getattr(for_update, "key_share", False) is not True
            )
            bound = tuple(str(parameter) for parameter in (parameters or ()))
            statements.append((statement, locked, bound))

        event.listen(engine.sync_engine, "before_cursor_execute", record)
        try:
            if case == "claim":
                await quest_service.claim_quest_rewards(session, side, vault_id)
            elif case in ("assign_existing", "assign_missing"):
                await quest_service.assign_quest_to_vault(
                    db_session=session, quest_id=side, vault_id=vault_id, is_visible=True
                )
            elif case == "list_backfill":
                await crud.quest_crud.get_multi_for_vault(db_session=session, skip=0, limit=100, vault_id=vault_id)
            else:
                await ensure_current_quest_rotation(session, vault_id)
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", record)

    vault_locks = _vault_lock_index(statements)
    link_ops = _link_op_index(statements)
    assert vault_locks, f"{case}: the writer must read the vault row FOR UPDATE"
    assert link_ops, f"{case}: the writer must lock or write a quest-link row"
    assert vault_locks[0] < link_ops[0], f"{case}: the vault lock must precede the first link op"
    assert statements[vault_locks[0]][2][:1] == (str(vault_id),), (
        f"{case}: the writer must lock the target vault row with FOR UPDATE"
    )
    assert not any(
        sql == "__commit__" and vault_locks[0] < i < link_ops[0] for i, (sql, _locked, _bound) in enumerate(statements)
    ), f"{case}: the vault lock and the link op must share one transaction"

    async with maker() as reader:
        link = await crud.quest_crud.get_link(reader, quest_id=daily if case == "rotation" else side, vault_id=vault_id)
    assert link is not None
    if case == "claim":
        assert link.is_completed
    elif case != "rotation":
        assert link.is_visible


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.integration
async def test_link_insert_conflict_keeps_first_row(quest_rows) -> None:
    """A lost insert race is a no-op: the first committed link row survives unchanged."""
    _, maker, vault_id, side, _ = quest_rows
    async with maker() as first:
        await crud.quest_crud.insert_links_if_absent(first, vault_id, {side: True})
        await first.commit()
    async with maker() as second:
        await crud.quest_crud.insert_links_if_absent(second, vault_id, {side: False})
        await second.commit()

    async with maker() as reader:
        link = (
            await reader.exec(select(VaultQuestCompletionLink).where(VaultQuestCompletionLink.vault_id == vault_id))
        ).one()
    assert link.is_visible is True
