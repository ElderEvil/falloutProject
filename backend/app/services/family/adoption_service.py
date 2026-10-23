"""Automatic adoption of orphaned children and teens by committed couples."""

import logging

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import dweller as crud_dweller
from app.crud.relationship import relationship_crud as crud_relationship
from app.crud.vault import vault as vault_crud
from app.models.notification import NotificationType
from app.services.bio_service import bio_service
from app.services.notification_service import notification_service
from app.utils.bios import render_adopted_child_bio

logger = logging.getLogger(__name__)


class AdoptionService:
    """Pair orphaned youth with committed, living couples during the family tick."""

    async def process_adoptions(self, db_session: AsyncSession, vault_id: UUID4) -> int:
        orphans = await crud_dweller.get_orphaned_youth(db_session, vault_id)
        if not orphans:
            return 0
        couples = await crud_relationship.get_committed_both_alive(db_session, vault_id)
        if not couples:
            return 0
        vault = await vault_crud.get(db_session, vault_id)
        if vault is None:
            return 0

        adopted = 0
        for index, child in enumerate(orphans):
            first_parent, second_parent = couples[index % len(couples)]
            child.parent_1_id = first_parent.id
            child.parent_2_id = second_parent.id
            db_session.add(child)
            await db_session.flush()

            bio_text = render_adopted_child_bio(
                f"{first_parent.first_name} {first_parent.last_name}",
                f"{second_parent.first_name} {second_parent.last_name}",
                str(first_parent.id),
                str(second_parent.id),
                str(vault_id),
            )
            await bio_service.append_entry(db_session, child.id, "family", bio_text)
            await notification_service.create_and_send(
                db_session,
                vault.user_id,
                NotificationType.CHILD_ADOPTED,
                "Child adopted",
                f"{first_parent.first_name} {first_parent.last_name} and {second_parent.first_name} {second_parent.last_name} adopted {child.first_name} {child.last_name}.",
                vault_id=vault_id,
                from_dweller_id=child.id,
                commit=False,
            )
            adopted += 1

        logger.info("Adopted %d orphaned youth in vault %s", adopted, vault_id)
        return adopted


adoption_service = AdoptionService()
