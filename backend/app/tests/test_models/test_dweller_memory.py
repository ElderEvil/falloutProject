"""Dweller memory model: one durable first-person fact per dweller.

The table is created by the Task 3 migration; these tests pin the model to it so a
drifted column or constraint fails here rather than at deploy time.
"""

import pytest
from sqlalchemy import Text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.chat_message import chat_message as chat_message_crud
from app.models.chat_message import ChatMessage, ChatMessageCreate
from app.models.dweller import Dweller
from app.models.dweller_memory import DwellerMemory
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate


async def test_dweller_memory_defaults_and_uuid7_id(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    memory = DwellerMemory(dweller_id=dweller.id, fact="I keep a lucky wrench under my bunk.", fact_hash="a" * 64)
    assert memory.id.version == 7
    assert memory.source_message_id is None
    async_session.add(memory)
    await async_session.flush()
    assert memory.created_at is not None
    assert memory.updated_at is not None


async def test_dweller_memory_duplicate_fact_hash_per_dweller_rejected(
    async_session: AsyncSession, dweller: Dweller
) -> None:
    async_session.add(DwellerMemory(dweller_id=dweller.id, fact="I fear the dark.", fact_hash="b" * 64))
    await async_session.commit()
    async_session.add(DwellerMemory(dweller_id=dweller.id, fact="I fear the dark!", fact_hash="b" * 64))
    with pytest.raises(IntegrityError):
        await async_session.flush()
    await async_session.rollback()


async def test_dweller_memory_allows_same_hash_for_another_dweller(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    other = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    async_session.add(DwellerMemory(dweller_id=dweller.id, fact="I fear the dark.", fact_hash="c" * 64))
    async_session.add(DwellerMemory(dweller_id=other.id, fact="I fear the dark.", fact_hash="c" * 64))
    await async_session.flush()


async def test_dweller_memory_links_source_message(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    await async_session.refresh(vault, ["user"])
    message = await chat_message_crud.create_message(
        async_session,
        obj_in=ChatMessageCreate(
            vault_id=vault.id,
            from_user_id=vault.user.id,
            to_dweller_id=dweller.id,
            message_text="Tell me about yourself",
        ),
    )
    memory = DwellerMemory(
        dweller_id=dweller.id,
        fact="I keep a lucky wrench under my bunk.",
        fact_hash="d" * 64,
        source_message_id=message.id,
    )
    async_session.add(memory)
    await async_session.commit()
    memory_id = memory.id
    async_session.expunge_all()
    reloaded = await async_session.get(DwellerMemory, memory_id)
    if reloaded is None:
        raise AssertionError("memory row vanished after commit")
    assert reloaded.source_message_id == message.id
    assert reloaded.fact == "I keep a lucky wrench under my bunk."


async def test_dweller_memory_nullable_source_message(async_session: AsyncSession, dweller: Dweller) -> None:
    async_session.add(DwellerMemory(dweller_id=dweller.id, fact="I sleep with the lights on.", fact_hash="e" * 64))
    await async_session.flush()


def test_dweller_memory_shape_matches_migration() -> None:
    """The migration wired the table; the model must not add or drop anything."""
    table = SQLModel.metadata.tables["dweller_memory"]
    assert table.name == "dweller_memory"

    columns = {column.name: column for column in table.columns}
    assert set(columns) == {"id", "dweller_id", "fact", "fact_hash", "source_message_id", "created_at", "updated_at"}
    assert isinstance(columns["fact"].type, Text)
    assert columns["fact"].nullable is False
    assert columns["fact_hash"].type.length == 64
    assert columns["fact_hash"].nullable is False
    assert columns["source_message_id"].nullable is True
    assert columns["id"].primary_key is True

    unique = {constraint.name: tuple(sorted(c.name for c in constraint.columns)) for constraint in table.constraints}
    assert unique["uq_memory_fact"] == ("dweller_id", "fact_hash")

    indexes = {index.name for index in table.indexes}
    assert indexes == {"ix_dweller_memory_id", "ix_dweller_memory_dweller_id"}

    dweller_fk = next(key for key in table.foreign_keys if key.parent.name == "dweller_id")
    assert dweller_fk.ondelete == "CASCADE"
    assert dweller_fk.column.table.name == "dweller"
    source_fk = next(key for key in table.foreign_keys if key.parent.name == "source_message_id")
    assert source_fk.column.table.name == "chatmessage"

    ddl = str(CreateTable(table).compile())
    assert "uq_memory_fact" in ddl
    assert "ON DELETE CASCADE" in ddl
    assert "VARCHAR(64)" in ddl
