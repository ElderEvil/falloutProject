"""Explicit support operations; gameplay changes keep their normal service rules."""

import logging
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.training import training as training_crud
from app.models.user import User
from app.models.vault import Vault
from app.services.exploration_service import exploration_service
from app.services.game_loop import game_loop_service
from app.services.training_service import training_service
from app.utils.exceptions import AccessDeniedException, ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)

INCIDENT_BATCH_SIZE = 50


async def perform_support_action(
    session: AsyncSession, identity: str, operation: str, record_id: UUID, *, actor_id: str
) -> None:
    match identity, operation:
        case "user", "verify-email" | "promote-superuser" | "soft-delete":
            await _update_user(session, operation, record_id, actor_id)
        case "vault", "pause" | "resume":
            await crud.vault.get(session, record_id)
            if operation == "pause":
                await game_loop_service.pause_vault(session, record_id)
            else:
                await game_loop_service.resume_vault(session, record_id)
        case "training", "cancel-training":
            await training_service.cancel_training(session, record_id)
        case "exploration", "recall":
            await exploration_service.start_return(session, record_id, recalled=True)
        case _:
            raise ValidationException("Unsupported admin action")
    logger.info("Admin %s performed %s on %s %s", actor_id, operation, identity, record_id)


async def describe_support_target(session: AsyncSession, identity: str, record_id: UUID) -> str:
    """Show the actual target before confirmation, without changing its state."""
    match identity:
        case "user":
            user = await crud.user.get(session, record_id)
            return f"{user.username} ({user.email})"
        case "vault":
            vault = await crud.vault.get(session, record_id)
            return str(vault)
        case "training":
            training = await training_crud.get(session, record_id)
            dweller = await crud.dweller.get(session, training.dweller_id)
            return f"{dweller.display_name}: {training.stat_being_trained.value} ({training.status.value})"
        case "exploration":
            exploration = await crud.exploration.get(session, record_id)
            dweller = await crud.dweller.get(session, exploration.dweller_id)
            return f"{dweller.display_name} ({exploration.status.value})"
        case _:
            raise ValidationException("Unsupported admin action")


async def list_incident_controls(session: AsyncSession, page: int) -> list[Vault]:
    if page < 1:
        raise ValidationException("Invalid page number")
    return await crud.vault.list_incident_controls(
        session, skip=(page - 1) * INCIDENT_BATCH_SIZE, limit=INCIDENT_BATCH_SIZE + 1
    )


async def set_incident_controls(
    session: AsyncSession, *, disabled: bool, vault_ids: list[UUID] | None, actor_id: str
) -> int:
    if vault_ids is not None and not 1 <= len(vault_ids) <= INCIDENT_BATCH_SIZE:
        raise ValidationException(
            f"Select between 1 and {INCIDENT_BATCH_SIZE} vaults, or explicitly choose all vaults."
        )
    count = await crud.vault.set_incidents_disabled(session, disabled=disabled, vault_ids=vault_ids)
    await session.commit()
    logger.info("Admin %s set incidents_disabled=%s for %s vaults", actor_id, disabled, count)
    return count


async def _update_user(session: AsyncSession, operation: str, record_id: UUID, actor_id: str) -> None:
    users = {user.id: user for user in await crud.user.get_by_ids_for_update(session, [UUID(actor_id), record_id])}
    actor = users.get(UUID(actor_id))
    if actor is None or not crud.user.is_active(actor) or not actor.is_superuser:
        raise AccessDeniedException
    target = users.get(record_id)
    if target is None or target.is_deleted:
        raise ResourceNotFoundException(User, identifier=record_id)
    if operation == "soft-delete":
        if target.id == actor.id:
            raise ValidationException("You cannot soft-delete the account you are using.")
        vaults = await crud.vault.get_by_user_id(db_session=session, user_id=target.id)
        await crud.game_state_crud.pause_many(session, [vault.id for vault in vaults])
        target.soft_delete()
        target.is_active = False
        target.email_verification_token = None
        target.password_reset_token = None
        target.password_reset_expires = None
    elif operation == "promote-superuser":
        target.is_superuser = True
    else:
        target.email_verified = True
        target.email_verification_token = None
    await session.commit()
