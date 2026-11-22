"""Query-budget regression for the vault quest read path.

The read path used to evaluate every requirement with one to four SQL statements per requirement, so a
vault with hundreds of quests burned thousands of queries per request. Requirement evaluation now runs over
one ``VaultFacts`` snapshot per request; these tests pin the statement count so the N+1 cannot come back.
"""

from collections.abc import Generator
from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.enums import RequirementType
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement
from app.models.room import Room
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.progression.quests.availability import get_quests_for_vault
from app.services.progression.quests.requirements import load_vault_facts, vault_missing_requirements
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.rooms import create_overseers_office
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


@contextmanager
def _count_statements(session: AsyncSession) -> Generator[list[str]]:
    """Collect every SQL statement the session's engine executes inside the block."""
    statements: list[str] = []
    bind = session.bind
    assert bind is not None
    engine = bind.sync_engine if hasattr(bind, "sync_engine") else bind.engine.sync_engine

    def _listener(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _listener)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", _listener)


async def _vault_with_office_and_dwellers(session: AsyncSession, *, dweller_count: int = 3, level: int = 10):
    user = await crud.user.create(session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    session.add(Room(**create_overseers_office(), vault_id=vault.id))
    for _ in range(dweller_count):
        dweller_data = create_fake_adult_dweller()
        dweller_data["level"] = level
        session.add(Dweller(**dweller_data, vault_id=vault.id))
    await session.commit()
    return vault


async def _seed_quests(session: AsyncSession, vault_id, count: int, *, offset: int = 0) -> None:
    """Assign ``count`` quests with met LEVEL + DWELLER_COUNT requirements to the vault."""
    quests = []
    for i in range(offset, offset + count):
        quest = Quest(
            title=f"Budget Quest {i}",
            short_description="Query budget",
            long_description="A quest used to count statements on the read path.",
            requirements="None",
            rewards="100 caps",
            quest_type="side",
        )
        session.add(quest)
        quests.append(quest)
    await session.commit()
    for quest in quests:
        await session.refresh(quest)
        session.add(
            QuestRequirement(
                quest_id=quest.id,
                requirement_type=RequirementType.LEVEL,
                requirement_data={"level": 5, "count": 1},
                is_mandatory=True,
            )
        )
        session.add(
            QuestRequirement(
                quest_id=quest.id,
                requirement_type=RequirementType.DWELLER_COUNT,
                requirement_data={"count": 1},
                is_mandatory=True,
            )
        )
    await session.commit()
    for quest in quests:
        await crud.quest_crud.assign_to_vault(session, quest.id, vault_id, is_visible=True)


@pytest.mark.asyncio
async def test_vault_quest_read_statement_count_is_constant_in_quest_count(async_session: AsyncSession) -> None:
    """The vault quest read costs a fixed handful of statements, not one set per quest."""
    vault = await _vault_with_office_and_dwellers(async_session)
    vault_id = vault.id
    await _seed_quests(async_session, vault_id, 60)

    async_session.expire_all()
    with _count_statements(async_session) as statements_60:
        reads_60 = await get_quests_for_vault(async_session, vault_id, 0, 500)

    assert len(reads_60) == 60
    assert all(not quest_read.is_locked for quest_read in reads_60)

    await _seed_quests(async_session, vault_id, 60, offset=60)
    async_session.expire_all()
    with _count_statements(async_session) as statements_120:
        reads_120 = await get_quests_for_vault(async_session, vault_id, 0, 500)

    assert len(reads_120) == 120
    assert all(not quest_read.is_locked for quest_read in reads_120)

    # 60 -> 120 quests doubles the requirement work the old code did per requirement per quest.
    assert len(statements_60) <= 20, statements_60
    assert len(statements_120) <= 20, statements_120
    assert len(statements_120) <= len(statements_60) + 2, (len(statements_60), len(statements_120))


@pytest.mark.asyncio
async def test_vault_facts_load_is_bounded(async_session: AsyncSession) -> None:
    """The snapshot itself is a small fixed set of aggregate queries."""
    vault = await _vault_with_office_and_dwellers(async_session)
    vault_id = vault.id
    async_session.expire_all()

    with _count_statements(async_session) as statements:
        facts = await load_vault_facts(async_session, vault_id)

    assert facts.alive_dweller_count == 3
    assert len(statements) <= 8, statements


@pytest.mark.asyncio
async def test_vault_missing_requirements_reports_the_same_descriptions(async_session: AsyncSession) -> None:
    """Every requirement type keeps its message, and the report keeps requirement order."""
    vault = await _vault_with_office_and_dwellers(async_session, dweller_count=0)
    prerequisite_id = uuid4()
    quest = Quest(
        title="Multi Gate",
        short_description="Many gates",
        long_description="A quest with one requirement of every vault-scoped type.",
        requirements="None",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    graded_requirements = (
        (RequirementType.LEVEL, {"level": 99, "count": 1}, "Need a dweller at level 99 or higher"),
        (RequirementType.ITEM, {"item_name": "Vault Suit", "count": 2}, "Need 2x Vault Suit owned or equipped"),
        (RequirementType.ROOM, {"room_type": "hydroponics"}, "Need Hydroponics built"),
        (RequirementType.DWELLER_COUNT, {"count": 5}, "Need at least 5 dwellers in vault"),
        (RequirementType.STAT, {"stat": "strength", "value": 99}, "Need a dweller with Strength 99+"),
        (RequirementType.ATTACK, {"attack": 50, "count": 1}, "Need a dweller with 50+ attack"),
        (
            RequirementType.QUEST_COMPLETED,
            {"quest_id": str(prerequisite_id)},
            f"Need to complete prerequisite quest (ID: {prerequisite_id})",
        ),
    )
    for requirement_type, requirement_data, _ in graded_requirements:
        async_session.add(
            QuestRequirement(
                quest_id=quest.id,
                requirement_type=requirement_type,
                requirement_data=requirement_data,
                is_mandatory=True,
            )
        )
    await async_session.commit()
    await async_session.refresh(quest, ["quest_requirements"])

    missing = await vault_missing_requirements(
        async_session, vault.id, quest, facts=await load_vault_facts(async_session, vault.id)
    )

    assert missing == [expected for _, _, expected in graded_requirements]


@pytest.mark.asyncio
async def test_available_and_blocked_quests_still_read_correctly(async_session: AsyncSession) -> None:
    """Behavioural guard: a met gate stays available, an unmet one keeps its exact lock reason."""
    vault = await _vault_with_office_and_dwellers(async_session, dweller_count=2, level=10)
    available_quest = Quest(
        title="Open Gate",
        short_description="Level 10",
        long_description="Needs a level 10 dweller.",
        requirements="None",
        rewards="100 caps",
        quest_type="side",
    )
    blocked_quest = Quest(
        title="Blocked Gate",
        short_description="Level 15",
        long_description="Needs a level 15 dweller.",
        requirements="None",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(available_quest)
    async_session.add(blocked_quest)
    await async_session.commit()
    await async_session.refresh(available_quest)
    await async_session.refresh(blocked_quest)
    async_session.add(
        QuestRequirement(
            quest_id=available_quest.id,
            requirement_type=RequirementType.LEVEL,
            requirement_data={"level": 10, "count": 2},
            is_mandatory=True,
        )
    )
    async_session.add(
        QuestRequirement(
            quest_id=blocked_quest.id,
            requirement_type=RequirementType.LEVEL,
            requirement_data={"level": 15, "count": 1},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    for quest in (available_quest, blocked_quest):
        await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    quest_reads = await get_quests_for_vault(async_session, vault.id, 0, 100)
    by_title = {quest_read.title: quest_read for quest_read in quest_reads}

    assert by_title["Open Gate"].is_locked is False
    assert by_title["Open Gate"].lock_reason is None
    assert by_title["Blocked Gate"].is_locked is True
    assert by_title["Blocked Gate"].lock_reason == "Need a dweller at level 15 or higher"
