"""get_or_create races: a losing creator must recover the winner's row, not 500."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import RoomTypeEnum
from app.crud.arena_state import CRUDArenaState
from app.crud.game_state import CRUDGameState
from app.models.arena_state import ArenaState
from app.models.room import Room
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.rooms import create_fake_room
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


async def _make_vault(async_session: AsyncSession):
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    return await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))


@pytest.mark.asyncio
@pytest.mark.parametrize("commit", [True, False], ids=["commit", "flush"])
async def test_game_state_get_or_create_recovers_from_create_race(async_session: AsyncSession, commit: bool) -> None:
    """A loser whose INSERT hits the unique constraint re-selects the winner's row.

    Staged race: the row exists, but the loser's pre-insert SELECT ran before the
    winner committed and returned None (monkeypatched to replay that stale view).
    The insert raises IntegrityError; get_or_create must roll back to a savepoint,
    re-select, and return the winner's row instead of propagating a 500.
    """
    vault = await _make_vault(async_session)

    # The winner: a GameState row really exists (committed by a concurrent request).
    await crud.game_state_crud.get_or_create(async_session, vault.id)

    real_get = crud.game_state_crud.get_by_vault_id
    calls = {"n": 0}

    async def stale_none_get(session, vault_id):
        # First call (the race loser's stale view): see nothing. Later calls
        # (re-select after the constraint hit): the row is really there.
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return await real_get(session, vault_id)

    monkey = pytest.MonkeyPatch()
    monkey.setattr(CRUDGameState, "get_by_vault_id", staticmethod(stale_none_get))
    try:
        state = await crud.game_state_crud.get_or_create(async_session, vault.id, commit=commit)
    finally:
        monkey.undo()

    assert state.vault_id == vault.id
    assert calls["n"] == 2  # stale pre-insert view + recovery re-select after ON CONFLICT no-op
    if not commit:
        # flush path: the caller's transaction must stay usable afterwards
        await async_session.commit()
    recovered = await crud.game_state_crud.get_by_vault_id(async_session, vault.id)
    from sqlalchemy import inspect as _i

    print(
        "RECOVERED-STATE expired=",
        _i(recovered).expired if recovered else None,
        "id=",
        recovered.id if recovered else None,
    )
    assert recovered is not None
    assert recovered.id == state.id


@pytest.mark.asyncio
async def test_arena_state_get_or_create_recovers_from_create_race(async_session: AsyncSession) -> None:
    """Same race treatment for ArenaState (per-room unique constraint)."""
    vault = await _make_vault(async_session)
    room_data = create_fake_room()
    room_data.update(name="Arena", category=RoomTypeEnum.ARENA, size=3, size_min=1, size_max=3)
    room = Room(vault_id=vault.id, **room_data)
    async_session.add(room)
    await async_session.commit()

    # The winner: an ArenaState row really exists (committed by a concurrent request).
    existing = ArenaState(room_id=room.id)
    async_session.add(existing)
    await async_session.commit()

    real_get = crud.arena_state_crud.get
    calls = {"n": 0}

    async def stale_none_get(session, room_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return await real_get(session, room_id)

    monkey = pytest.MonkeyPatch()
    monkey.setattr(CRUDArenaState, "get", staticmethod(stale_none_get))
    try:
        state = await crud.arena_state_crud.get_or_create(async_session, room.id)
    except IntegrityError:
        raise AssertionError("get_or_create propagated the race instead of recovering") from None
    finally:
        monkey.undo()

    assert state.room_id == room.id
    recovered = await crud.arena_state_crud.get(async_session, room.id)
    assert recovered is not None
    assert recovered.room_id == state.room_id
