"""Service for safely transferring dwellers between vaults."""

import logging

from pydantic import UUID4
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.dweller import dweller as dweller_crud
from app.crud.relationship import relationship_crud
from app.models.dweller import Dweller
from app.models.pregnancy import Pregnancy
from app.models.relationship import Relationship
from app.schemas.common import PARTNER_LINKED_STAGES
from app.utils.exceptions import ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)


class TransferService:
    @staticmethod
    async def _break_partner_link(db_session: AsyncSession, dweller: Dweller, partner_id: UUID4) -> None:
        if dweller.partner_id == partner_id:
            dweller.partner_id = None
        try:
            partner = await dweller_crud.get(db_session, partner_id)
            if partner.partner_id == dweller.id:
                partner.partner_id = None
                db_session.add(partner)
        except ResourceNotFoundException:
            pass

    @staticmethod
    async def _delete_relationship_with_unlink(
        db_session: AsyncSession, rel: Relationship, dweller: Dweller, other_id: UUID4
    ) -> None:
        if rel.relationship_type in PARTNER_LINKED_STAGES:
            await TransferService._break_partner_link(db_session, dweller, other_id)
        await db_session.delete(rel)

    @staticmethod
    async def _cancel_pregnancies_for_transfer(
        db_session: AsyncSession, dweller: Dweller, transferring_ids: set[UUID4]
    ) -> None:
        pregnancies = (
            (
                await db_session.execute(
                    select(Pregnancy)
                    .where((Pregnancy.mother_id == dweller.id) | (Pregnancy.father_id == dweller.id))
                    .where(Pregnancy.status == "pregnant")
                )
            )
            .scalars()
            .all()
        )
        for preg in pregnancies:
            other_parent = preg.father_id if preg.mother_id == dweller.id else preg.mother_id
            if other_parent not in transferring_ids:
                await db_session.delete(preg)
                logger.info("Cancelled cross-vault pregnancy %s due to transfer of %s", preg.id, dweller.id)

    @staticmethod
    def _reset_for_transfer(dweller: Dweller, dest_vault_id: UUID4) -> None:
        dweller.room_id = None
        dweller.status = "idle"
        dweller.apprentice_stat = None
        dweller.apprentice_started_at = None
        dweller.apprentice_stat_gains = {}
        dweller.vault_id = dest_vault_id

    @staticmethod
    async def transfer_dwellers(
        db_session: AsyncSession,
        dweller_ids: list[UUID4],
        dest_vault_id: UUID4,
    ) -> list[Dweller]:
        """Move dwellers to another vault, cleaning up cross-vault state."""
        from app.crud.vault import vault as vault_crud

        if not dweller_ids:
            msg = "No dwellers specified for transfer"
            raise ValidationException(msg)

        dest_vault = await vault_crud.get(db_session, dest_vault_id)

        unique_ids = list(dict.fromkeys(dweller_ids))
        transferring_ids = set(unique_ids)
        dwellers: list[Dweller] = []
        for did in unique_ids:
            d = await dweller_crud.get(db_session, did)
            if d.is_deleted:
                msg = f"Dweller {did} is deleted and cannot be transferred"
                raise ValidationException(msg)
            if d.vault_id == dest_vault_id:
                msg = f"Dweller {did} already in destination vault"
                raise ValidationException(msg)
            dwellers.append(d)

        if dest_vault.population_max is not None:
            dest_pop = await vault_crud.get_population(db_session=db_session, vault_id=dest_vault_id)
            if dest_pop + len(dwellers) > dest_vault.population_max:
                msg = f"Destination vault full: {dest_pop}/{dest_vault.population_max} with {len(dwellers)} incoming"
                raise ValidationException(msg)

        for dweller in dwellers:
            for rel in await relationship_crud.get_by_dweller(db_session, dweller.id):
                other_id = rel.dweller_2_id if rel.dweller_1_id == dweller.id else rel.dweller_1_id
                if other_id in transferring_ids:
                    continue
                await TransferService._delete_relationship_with_unlink(db_session, rel, dweller, other_id)

            await TransferService._cancel_pregnancies_for_transfer(db_session, dweller, transferring_ids)
            TransferService._reset_for_transfer(dweller, dest_vault_id)
            db_session.add(dweller)

        await db_session.commit()
        for d in dwellers:
            await db_session.refresh(d)
        logger.info("Transferred %s dwellers to vault %s", len(dwellers), dest_vault_id)
        return dwellers

    @staticmethod
    async def cleanup_cross_vault_relationships(db_session: AsyncSession, vault_id: UUID4) -> int:
        """Delete relationships where dwellers belong to different vaults."""
        from sqlalchemy.orm import aliased

        d1 = aliased(Dweller)
        d2 = aliased(Dweller)
        q = (
            select(Relationship)
            .join(d1, Relationship.dweller_1_id == d1.id)
            .join(d2, Relationship.dweller_2_id == d2.id)
            .where(d1.vault_id != d2.vault_id)
            .where((d1.vault_id == vault_id) | (d2.vault_id == vault_id))
        )
        orphans = (await db_session.execute(q)).scalars().all()
        count = 0
        for rel in orphans:
            d1_obj = await db_session.get(Dweller, rel.dweller_1_id)
            d2_obj = await db_session.get(Dweller, rel.dweller_2_id)
            if rel.relationship_type in PARTNER_LINKED_STAGES:
                if d1_obj and d2_obj:
                    await TransferService._break_partner_link(db_session, d1_obj, d2_obj.id)
                    await TransferService._break_partner_link(db_session, d2_obj, d1_obj.id)
                elif d1_obj:
                    d1_obj.partner_id = None
                    db_session.add(d1_obj)
                elif d2_obj:
                    d2_obj.partner_id = None
                    db_session.add(d2_obj)
            await db_session.delete(rel)
            count += 1
        if count:
            await db_session.commit()
            logger.info("Cleaned %s cross-vault relationships for vault %s", count, vault_id)
        return count


transfer_service = TransferService()
