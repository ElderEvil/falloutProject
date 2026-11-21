"""Duel service rules: expiry, one open slot, one notification, dwellers untouched."""

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import NotificationType, PvpDuelStatus
from app.crud import pvp_duel as pvp_duel_crud
from app.models.dweller import Dweller
from app.models.notification import Notification
from app.models.vault import Vault
from app.services.pvp_duel_service import pvp_duel_service
from app.utils.exceptions import ResourceConflictException, ValidationException
from app.utils.time import utcnow

COMBAT_TYPES = [NotificationType.COMBAT_VICTORY, NotificationType.COMBAT_DEFEAT]


async def _dweller_rows(db_session: AsyncSession, vault_ids: list) -> list[tuple]:
    columns = list(Dweller.__table__.columns)
    result = await db_session.execute(select(*columns).where(Dweller.vault_id.in_(vault_ids)).order_by(Dweller.id))
    return [tuple(row) for row in result.all()]


async def _expire(db_session: AsyncSession, duel_id) -> None:
    duel = await pvp_duel_crud.get_duel(db_session, duel_id)
    assert duel is not None
    duel.expires_at = utcnow() - timedelta(minutes=1)
    db_session.add(duel)
    await db_session.commit()


async def test_accept_after_expires_at_is_rejected_and_marks_expired(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, user_with_vault: tuple, dweller_in_vault: Dweller
) -> None:
    _, defender_vault = user_with_vault
    read = await pvp_duel_service.post(async_session, vault.id, dweller_ids=[dweller.id])
    await _expire(async_session, read.duel_id)

    with pytest.raises(ValidationException):
        await pvp_duel_service.accept(async_session, defender_vault.id, read.duel_id, dweller_ids=[dweller_in_vault.id])

    duel = await pvp_duel_crud.get_duel(async_session, read.duel_id)
    assert duel is not None
    assert PvpDuelStatus(duel.status) == PvpDuelStatus.EXPIRED
    assert duel.defender_snapshot is None
    assert duel.outcome is None


async def test_one_open_duel_per_challenger_and_lazy_slot_release(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    first = await pvp_duel_service.post(async_session, vault.id, dweller_ids=[dweller.id])

    with pytest.raises(ResourceConflictException):
        await pvp_duel_service.post(async_session, vault.id, dweller_ids=[dweller.id])

    await _expire(async_session, first.duel_id)
    second = await pvp_duel_service.post(async_session, vault.id, dweller_ids=[dweller.id])

    expired = await pvp_duel_crud.get_duel(async_session, first.duel_id)
    assert expired is not None
    assert PvpDuelStatus(expired.status) == PvpDuelStatus.EXPIRED
    assert PvpDuelStatus(second.status) == PvpDuelStatus.OPEN


async def test_settlement_writes_one_notification_and_leaves_dwellers_identical(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, user_with_vault: tuple, dweller_in_vault: Dweller
) -> None:
    _, defender_vault = user_with_vault
    vault_ids = [vault.id, defender_vault.id]
    before = await _dweller_rows(async_session, vault_ids)

    read = await pvp_duel_service.post(async_session, vault.id, dweller_ids=[dweller.id])
    settled = await pvp_duel_service.accept(
        async_session, defender_vault.id, read.duel_id, dweller_ids=[dweller_in_vault.id]
    )

    assert PvpDuelStatus(settled.status) == PvpDuelStatus.ACCEPTED
    assert settled.outcome in {"challenger", "defender"}
    assert settled.journal
    assert settled.defender_party is not None

    result = await async_session.execute(
        select(Notification).where(
            Notification.user_id == vault.user_id,
            Notification.notification_type.in_(COMBAT_TYPES),
        )
    )
    notifications = list(result.scalars().all())
    assert len(notifications) == 1
    expected = NotificationType.COMBAT_VICTORY if settled.outcome == "challenger" else NotificationType.COMBAT_DEFEAT
    assert notifications[0].notification_type == expected
    assert notifications[0].meta_data == {"duel_id": str(read.duel_id)}

    assert await _dweller_rows(async_session, vault_ids) == before


async def test_replay_is_stable_after_settlement(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, user_with_vault: tuple, dweller_in_vault: Dweller
) -> None:
    _, defender_vault = user_with_vault
    read = await pvp_duel_service.post(async_session, vault.id, dweller_ids=[dweller.id])
    await pvp_duel_service.accept(async_session, defender_vault.id, read.duel_id, dweller_ids=[dweller_in_vault.id])

    first = await pvp_duel_service.get(async_session, vault.id, read.duel_id)
    second = await pvp_duel_service.get(async_session, vault.id, read.duel_id)

    assert first.journal == second.journal
    assert first.outcome == second.outcome


async def test_party_is_explicit_and_capped_at_three(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Same contract as an expedition dispatch: the player names the party, 1-3, never the server."""
    with pytest.raises(ValidationException):
        await pvp_duel_service.post(async_session, vault.id, dweller_ids=[])

    with pytest.raises(ValidationException):
        await pvp_duel_service.post(async_session, vault.id, dweller_ids=[dweller.id] * 4)


async def test_one_dweller_cannot_fill_a_party(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """Duplicates would triple that dweller's power; the roster is a set, not a list."""
    with pytest.raises(ValidationException):
        await pvp_duel_service.post(async_session, vault.id, dweller_ids=[dweller.id] * 3)


async def test_accept_adopts_the_challenger_tuning(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    user_with_vault: tuple,
    dweller_in_vault: Dweller,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deploy between post and accept changes TUNING; the duel must still settle."""
    from app.services.pvp import snapshots

    _, defender_vault = user_with_vault
    read = await pvp_duel_service.post(async_session, vault.id, dweller_ids=[dweller.id])

    monkeypatch.setitem(snapshots.TUNING, "max_rounds", 3)
    settled = await pvp_duel_service.accept(
        async_session, defender_vault.id, read.duel_id, dweller_ids=[dweller_in_vault.id]
    )

    duel = await pvp_duel_crud.get_duel(async_session, read.duel_id)
    assert duel is not None
    assert duel.defender_snapshot is not None
    assert duel.defender_snapshot["tuning"] == duel.challenger_snapshot["tuning"]
    assert PvpDuelStatus(settled.status) == PvpDuelStatus.ACCEPTED


async def test_expiry_never_overwrites_a_settled_duel(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, user_with_vault: tuple, dweller_in_vault: Dweller
) -> None:
    """The conditional UPDATE is what keeps a late reader from erasing a result."""
    _, defender_vault = user_with_vault
    read = await pvp_duel_service.post(async_session, vault.id, dweller_ids=[dweller.id])
    await pvp_duel_service.accept(async_session, defender_vault.id, read.duel_id, dweller_ids=[dweller_in_vault.id])

    await pvp_duel_crud.expire_open(async_session, [read.duel_id], utcnow() + timedelta(days=1))
    await async_session.commit()

    duel = await pvp_duel_crud.get_duel(async_session, read.duel_id)
    assert duel is not None
    assert PvpDuelStatus(duel.status) == PvpDuelStatus.ACCEPTED
    assert duel.outcome is not None
