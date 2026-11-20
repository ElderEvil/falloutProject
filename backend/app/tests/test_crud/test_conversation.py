"""Conversation CRUD: lazy race-safe get_or_create and touch."""

from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.conversation import CRUDConversation
from app.models.conversation import Conversation
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.utils.time import utcnow


async def _ids(async_session: AsyncSession, vault: Vault) -> tuple[UUID, UUID]:
    await async_session.refresh(vault, ["user"])
    return vault.user.id, vault.id


async def _count(async_session: AsyncSession) -> int:
    return (await async_session.execute(select(func.count()).select_from(Conversation))).scalar_one()


async def test_get_or_create_creates_then_reuses_one_row(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    user_id, vault_id = await _ids(async_session, vault)
    first = await crud.conversation.get_or_create(
        async_session, vault_id=vault_id, user_id=user_id, dweller_id=dweller.id
    )
    assert first.id.version == 7
    assert first.message_count == 0
    second = await crud.conversation.get_or_create(
        async_session, vault_id=vault_id, user_id=user_id, dweller_id=dweller.id
    )
    assert second.id == first.id
    await async_session.flush()
    assert await _count(async_session) == 1


async def test_get_or_create_recovers_from_create_race(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Staged race (the repo pattern): the loser's pre-insert SELECT saw nothing, its INSERT
    hits the unique constraint, and it must re-select the winner's row instead of raising.
    """
    user_id, vault_id = await _ids(async_session, vault)
    winner = await crud.conversation.get_or_create(
        async_session, vault_id=vault_id, user_id=user_id, dweller_id=dweller.id
    )
    await async_session.flush()

    real_get = CRUDConversation.get_by_pair
    calls = {"n": 0}

    async def stale_none_get(self, db, *, user_id, dweller_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return await real_get(self, db, user_id=user_id, dweller_id=dweller_id)

    monkey = pytest.MonkeyPatch()
    monkey.setattr(CRUDConversation, "get_by_pair", stale_none_get)
    try:
        recovered = await crud.conversation.get_or_create(
            async_session, vault_id=vault_id, user_id=user_id, dweller_id=dweller.id
        )
    except IntegrityError:
        raise AssertionError("get_or_create propagated the race instead of recovering") from None
    finally:
        monkey.undo()

    assert calls["n"] == 2  # stale pre-insert view + recovery re-select
    assert recovered.id == winner.id
    # The caller's transaction must stay usable after the savepoint rollback.
    await async_session.flush()
    assert await _count(async_session) == 1


async def test_get_or_create_separates_dweller_pairs(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    user_id, vault_id = await _ids(async_session, vault)
    other = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault_id))
    first = await crud.conversation.get_or_create(
        async_session, vault_id=vault_id, user_id=user_id, dweller_id=dweller.id
    )
    second = await crud.conversation.get_or_create(
        async_session, vault_id=vault_id, user_id=user_id, dweller_id=other.id
    )
    assert first.id != second.id
    await async_session.flush()
    assert await _count(async_session) == 2


async def test_touch_bumps_count_and_timestamp(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    user_id, vault_id = await _ids(async_session, vault)
    conversation = await crud.conversation.get_or_create(
        async_session, vault_id=vault_id, user_id=user_id, dweller_id=dweller.id
    )
    at = utcnow()
    touched = await crud.conversation.touch(async_session, conversation, at=at)
    assert touched.message_count == 1
    assert touched.last_message_at == at
    later = utcnow()
    touched = await crud.conversation.touch(async_session, conversation, at=later, message_count=7)
    assert touched.message_count == 7
    assert touched.last_message_at == later
    await async_session.flush()
