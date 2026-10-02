from collections.abc import Sequence

from pydantic import UUID4
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.models.vault import Vault
from app.models.vault_slot import VaultSlot
from app.utils.exceptions import ResourceConflictException


class CRUDVaultSlot:
    async def claim_next(self, *, db_session: AsyncSession, vault_id: UUID4) -> VaultSlot:
        """Claim the lowest free slot for a vault, atomically.

        Candidate indices come from a single snapshot query, then each is inserted
        under a savepoint; the unique constraint on ``slot_index`` rejects a losing
        race, the savepoint rolls back so the next index is tried, and one commit
        makes the claim durable. Callers must have a transaction open (the flush
        before this call does); ``IntegrityError`` inside ``begin_nested`` is caught
        here because the savepoint rolls back before it propagates.
        """
        used = set((await db_session.execute(select(VaultSlot.slot_index))).scalars().all())
        for slot_index in range(game_config.vault_slots.count):
            if slot_index in used:
                continue
            slot = VaultSlot(slot_index=slot_index, vault_id=vault_id)
            try:
                async with db_session.begin_nested():
                    db_session.add(slot)
                    await db_session.flush()
            except IntegrityError:
                continue
            await db_session.commit()
            return slot
        raise ResourceConflictException("No vault slots are available.")

    async def claim_for_new_vault(self, *, db_session: AsyncSession, vault_id: UUID4) -> int:
        """Claim a slot without committing, for an enclosing vault transaction.

        Insert-only (no pre-read snapshot): each candidate is inserted under a
        savepoint and a unique-constraint violation rolls it back and tries the next
        index. Returns the claimed index; the caller's commit makes vault + slot
        durable together, so an allocation failure cannot leave a vault without a slot.
        """
        for slot_index in range(game_config.vault_slots.count):
            try:
                async with db_session.begin_nested():
                    await db_session.execute(insert(VaultSlot).values(slot_index=slot_index, vault_id=vault_id))
            except IntegrityError:
                continue
            return slot_index
        raise ResourceConflictException("No vault slots are available.")

    async def list_all(self, db_session: AsyncSession) -> Sequence[VaultSlot]:
        return (await db_session.execute(select(VaultSlot))).scalars().all()

    async def get_by_vault(self, db_session: AsyncSession, vault_id: UUID4) -> VaultSlot | None:
        return (
            await db_session.execute(select(VaultSlot).where(VaultSlot.vault_id == vault_id))
        ).scalar_one_or_none()

    async def list_markers(
        self, db_session: AsyncSession
    ) -> Sequence[tuple[int, UUID4, int, UUID4]]:
        """(slot_index, vault_id, vault number, owner user_id) for every live vault."""
        result = await db_session.execute(
            select(VaultSlot.slot_index, VaultSlot.vault_id, Vault.number, Vault.user_id)
            .join(Vault, Vault.id == VaultSlot.vault_id)
            .where(Vault.is_deleted == False)  # ruff: ignore[true-false-comparison]
        )
        return [(slot, vault_id, number, user_id) for slot, vault_id, number, user_id in result.all()]


vault_slot = CRUDVaultSlot()
