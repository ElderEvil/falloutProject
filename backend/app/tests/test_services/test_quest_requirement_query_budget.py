"""Query-budget regression for the vault quest read path (one VaultFacts snapshot per request)."""

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


def _base(**kw) -> dict:
    base = {
        "title": "Quest",
        "short_description": "Test",
        "long_description": "Test quest",
        "requirements": "None",
        "rewards": "100 caps",
    }
    return base | kw


@contextmanager
def _count_statements(session: AsyncSession) -> Generator[list[str]]:
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
        session.add(Dweller(**(create_fake_adult_dweller() | {"level": level}), vault_id=vault.id))
    await session.commit()
    return vault


async def _seed_quests(session: AsyncSession, vault_id, count: int, *, offset: int = 0) -> None:
    quests = [Quest(**_base(title=f"Budget Quest {i}")) for i in range(offset, offset + count)]
    session.add_all(quests)
    await session.commit()
    for quest in quests:
        await session.refresh(quest)
        session.add_all(
            [
                QuestRequirement(
                    quest_id=quest.id,
                    requirement_type=requirement_type,
                    requirement_data=requirement_data,
                    is_mandatory=True,
                )
                for requirement_type, requirement_data in (
                    (RequirementType.LEVEL, {"level": 5, "count": 1}),
                    (RequirementType.DWELLER_COUNT, {"count": 1}),
                )
            ]
        )
    await session.commit()
    for quest in quests:
        await crud.quest_crud.assign_to_vault(session, quest.id, vault_id, is_visible=True)


async def _level_quest(session: AsyncSession, vault, title: str, level: int, count: int) -> Quest:
    quest = Quest(**_base(title=title))
    session.add(quest)
    await session.commit()
    await session.refresh(quest)
    session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.LEVEL,
            requirement_data={"level": level, "count": count},
            is_mandatory=True,
        )
    )
    await session.commit()
    await crud.quest_crud.assign_to_vault(session, quest.id, vault.id, is_visible=True)
    return quest


async def test_vault_quest_read_statement_count_is_constant_in_quest_count(async_session: AsyncSession) -> None:
    vault_id = (await _vault_with_office_and_dwellers(async_session)).id
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


async def test_vault_facts_load_is_bounded(async_session: AsyncSession) -> None:
    vault_id = (await _vault_with_office_and_dwellers(async_session)).id
    async_session.expire_all()
    with _count_statements(async_session) as statements:
        facts = await load_vault_facts(async_session, vault_id)
    assert facts.alive_dweller_count == 3
    assert len(statements) <= 8, statements


async def test_vault_missing_requirements_reports_the_same_descriptions(async_session: AsyncSession) -> None:
    vault = await _vault_with_office_and_dwellers(async_session, dweller_count=0)
    prerequisite_id = uuid4()
    quest = await _level_quest(async_session, vault, "Multi Gate", 99, 1)
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
    for requirement_type, requirement_data, _ in graded_requirements[1:]:
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


async def test_available_and_blocked_quests_still_read_correctly(async_session: AsyncSession) -> None:
    vault = await _vault_with_office_and_dwellers(async_session, dweller_count=2, level=10)
    await _level_quest(async_session, vault, "Open Gate", 10, 2)
    await _level_quest(async_session, vault, "Blocked Gate", 15, 1)
    quest_reads = await get_quests_for_vault(async_session, vault.id, 0, 100)
    by_title = {quest_read.title: quest_read for quest_read in quest_reads}
    assert (by_title["Open Gate"].is_locked, by_title["Open Gate"].lock_reason) == (False, None)
    assert (by_title["Blocked Gate"].is_locked, by_title["Blocked Gate"].lock_reason) == (
        True,
        "Need a dweller at level 15 or higher",
    )
