"""Regression tests for ``CRUDBase.create``: conflict detection and transaction ownership.

Two defects are pinned here. A create schema without a ``name`` field must still produce a
``ResourceAlreadyExistsException`` (409) instead of an ``AttributeError`` raised from inside the
handler. And ``commit=False`` must flush and propagate without rolling back the caller's
transaction (docs/backend/SERVICE_LAYER.md: "recoverable nested attempts use a savepoint owned by
their caller").
"""

import pytest
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.conversation import ConversationBase
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.utils.exceptions import ResourceAlreadyExistsException


class NamedConversationCreate(ConversationBase):
    """Conversation payload that also exposes ``name``.

    ``Conversation`` has no ``name`` column, so the value is ignored by ``model_validate``; it only
    keeps the name-less message path out of the rollback assertions below.
    """

    name: str = "thread"


async def _conversation_in(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> ConversationBase:
    await async_session.refresh(vault, ["user"])
    return ConversationBase(vault_id=vault.id, user_id=vault.user.id, dweller_id=dweller.id)


async def _staged_dweller(async_session: AsyncSession, vault: Vault, dweller_data: dict) -> Dweller:
    """An earlier write by the caller that is flushed but deliberately not committed."""
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in, commit=False)


async def test_create_duplicate_without_name_field_raises_conflict(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    conversation_in = await _conversation_in(async_session, vault, dweller)
    await crud.conversation.create(db_session=async_session, obj_in=conversation_in)

    with pytest.raises(ResourceAlreadyExistsException) as exc_info:
        await crud.conversation.create(db_session=async_session, obj_in=conversation_in)

    # No name on the schema: the message falls back to the model class instead of exploding.
    assert "Conversation" in exc_info.value.detail


async def test_commit_false_conflict_keeps_the_callers_earlier_write_committable(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    dweller_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_in = await _conversation_in(async_session, vault, dweller)
    await crud.conversation.create(db_session=async_session, obj_in=conversation_in)
    earlier = await _staged_dweller(async_session, vault, dweller_data)
    assert earlier.id is not None

    async def conflicting_flush(self: AsyncSession, *args: object, **kwargs: object) -> None:
        # The staged INSERT hits the conversation unique pair; raise what the driver raises.
        raise IntegrityError(
            "INSERT INTO conversation",
            {},
            Exception("UNIQUE constraint failed: conversation.user_id, conversation.dweller_id"),
        )

    monkeypatch.setattr(AsyncSession, "flush", conflicting_flush)

    with pytest.raises(ResourceAlreadyExistsException):
        await crud.conversation.create(
            db_session=async_session,
            obj_in=NamedConversationCreate(**conversation_in.model_dump()),
            commit=False,
        )

    monkeypatch.undo()
    # The caller discards the row it knows failed; its earlier write was already flushed.
    async_session.expunge_all()
    await async_session.commit()
    assert await async_session.get(Dweller, earlier.id) is not None


async def test_caller_owned_savepoint_absorbs_the_conflict(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    conversation_in = await _conversation_in(async_session, vault, dweller)
    await crud.conversation.create(db_session=async_session, obj_in=conversation_in)
    earlier = await _staged_dweller(async_session, vault, dweller_data)

    savepoint = await async_session.begin_nested()
    with pytest.raises(ResourceAlreadyExistsException):
        await crud.conversation.create(
            db_session=async_session,
            obj_in=NamedConversationCreate(**conversation_in.model_dump()),
            commit=False,
        )
    try:
        await savepoint.rollback()
    except InvalidRequestError as exc:  # pragma: no cover - only reached when the defect returns
        pytest.fail(f"create() rolled back the caller's savepoint: {exc}")

    await async_session.commit()
    assert await async_session.get(Dweller, earlier.id) is not None
