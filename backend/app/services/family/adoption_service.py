"""Automatic adoption of orphaned children and teens by committed couples."""

import logging

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import GenderEnum
from app.crud import dweller as crud_dweller
from app.crud.relationship import relationship_crud as crud_relationship
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.notification import NotificationType
from app.services.bio_service import bio_service
from app.services.game_tick.guard import recover_session
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)


def _name(dweller: Dweller) -> str:
    return f"{dweller.first_name} {dweller.last_name or ''}".strip()


def _ordered_parents(first: Dweller, second: Dweller) -> tuple[Dweller, Dweller]:
    """Mother slot first for mixed-gender pairs, otherwise stable by id."""
    if first.gender != second.gender:
        if first.gender == GenderEnum.FEMALE:
            return first, second
        if second.gender == GenderEnum.FEMALE:
            return second, first
    return (first, second) if str(first.id) < str(second.id) else (second, first)


class AdoptionService:
    """Pair orphaned youth with committed, living couples during the family tick."""

    async def process_adoptions(self, db_session: AsyncSession, vault_id: UUID4) -> list[Dweller]:
        candidates = await crud_dweller.get_orphaned_youth(db_session, vault_id)
        if not candidates:
            return []
        parent_ids = {
            parent_id
            for child in candidates
            for parent_id in (child.parent_1_id, child.parent_2_id)
            if parent_id is not None
        }
        parents_by_id = {
            parent.id: parent
            for parent in await crud_dweller.get_by_ids(list(parent_ids), db_session, include_deleted=True)
        }
        orphans: list[Dweller] = []
        for child in candidates:
            parents = (parents_by_id.get(parent_id) for parent_id in (child.parent_1_id, child.parent_2_id))
            if all(parent is None or parent.is_dead or parent.is_deleted for parent in parents):
                orphans.append(child)
        if not orphans:
            return []

        couples = await crud_relationship.get_committed_both_alive(db_session, vault_id)
        vault = await vault_crud.get(db_session, vault_id)
        if not couples or vault is None:
            return []

        adopted: list[Dweller] = []
        try:
            for child, (first, second) in zip(orphans, couples, strict=False):
                first_parent, second_parent = _ordered_parents(first, second)
                child.parent_1_id = first_parent.id
                child.parent_2_id = second_parent.id
                bio_service.add_entry(
                    child,
                    "family",
                    f"Adopted by {_name(first_parent)} and {_name(second_parent)}.",
                    {
                        "adopter_1_id": str(first_parent.id),
                        "adopter_2_id": str(second_parent.id),
                        "adopted": True,
                    },
                )
                for parent in (first_parent, second_parent):
                    bio_service.add_entry(parent, "family", f"Adopted {_name(child)}.", {"child_id": str(child.id)})
                for dweller in (child, first_parent, second_parent):
                    db_session.add(dweller)
                await notification_service.create_and_send(
                    db_session,
                    vault.user_id,
                    NotificationType.CHILD_ADOPTED,
                    "Child adopted",
                    f"{_name(first_parent)} and {_name(second_parent)} adopted {_name(child)}.",
                    vault_id=vault_id,
                    from_dweller_id=child.id,
                    commit=False,
                )
                adopted.append(child)

            await db_session.commit()
        except Exception:
            await recover_session(db_session)
            raise
        await notification_service.deliver_deferred_notifications(db_session)
        logger.info("Adopted %d orphaned youth in vault %s", len(adopted), vault_id)
        return adopted


adoption_service = AdoptionService()
