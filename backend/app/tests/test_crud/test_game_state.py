"""Reproduction / regression test for the game_state CRUD session-type bug.

The dramatiq actors (``game_tick`` / ``process_vault_tick``) build a RAW
SQLAlchemy ``AsyncSession`` (``sqlalchemy.ext.asyncio.AsyncSession``) via
``async_sessionmaker``, which does NOT expose SQLModel's convenience
``.exec()`` method. ``game_state.py`` was the only CRUD module using ``.exec()``,
so every GameState lookup from a background actor raised
``AttributeError: 'AsyncSession' object has no attribute 'exec'`` — killing the
entire game tick before any per-vault work ran.

These tests exercise ``game_state_crud`` with a RAW SQLAlchemy ``AsyncSession``
(the exact type the actors hand it) so the regression cannot silently return.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import JSON, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession as RawAsyncSession,
)
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.crud.game_state import game_state_crud
from app.models.game_state import GameState


# sqlite has no JSONB; rewrite to JSON before creating tables (mirrors conftest).
@event.listens_for(SQLModel.metadata, "before_create")
def _replace_jsonb_with_json(target, connection, **kw):
    for table in target.tables.values():
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()


@pytest_asyncio.fixture
async def raw_sqlalchemy_session():
    """A RAW SQLAlchemy AsyncSession — the exact type the game_tick actor passes
    to game_state_crud. It has no ``.exec()``."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    session_maker = async_sessionmaker(engine, class_=RawAsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


async def test_get_by_vault_id_with_raw_async_session(raw_sqlalchemy_session):
    vault_id = uuid4()
    raw_sqlalchemy_session.add(GameState(vault_id=vault_id))
    await raw_sqlalchemy_session.commit()

    # Before the fix this raised:
    #   AttributeError: 'AsyncSession' object has no attribute 'exec'
    result = await game_state_crud.get_by_vault_id(raw_sqlalchemy_session, vault_id)

    assert result is not None
    assert result.vault_id == vault_id


async def test_get_or_create_with_raw_async_session(raw_sqlalchemy_session):
    vault_id = uuid4()

    created = await game_state_crud.get_or_create(raw_sqlalchemy_session, vault_id)

    assert created is not None
    assert created.vault_id == vault_id
    assert created.id is not None  # refreshed after insert
