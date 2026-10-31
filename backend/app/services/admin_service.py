"""Explicit support operations; gameplay changes keep their normal service rules."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.training import training as training_crud
from app.models.user import User
from app.models.vault import Vault
from app.schemas.user import UserCreate, UserUpdate
from app.services.exploration_service import exploration_service
from app.services.game_loop_service import game_loop_service
from app.services.training_service import training_service
from app.utils.exceptions import (
    AccessDeniedException,
    ResourceConflictException,
    ResourceNotFoundException,
    ValidationException,
)

logger = logging.getLogger(__name__)

INCIDENT_BATCH_SIZE = 50
FIRST_SUPERUSER_OPERATIONS = frozenset({"promote-superuser", "demote-superuser"})


def is_first_superuser(user: User) -> bool:
    """A durable bootstrap marker; email changes and promotions never transfer it."""
    return user.is_first_superuser


def _authorize_user_action(actor: User, target: User, operation: str) -> None:
    if not crud.user.is_active(actor) or not actor.is_superuser:
        raise AccessDeniedException
    if target.is_deleted:
        raise ResourceNotFoundException(User, identifier=target.id)
    if (operation in FIRST_SUPERUSER_OPERATIONS or target.is_superuser) and not is_first_superuser(actor):
        raise AccessDeniedException("Only the first superuser can manage administrator accounts or roles.")


async def perform_support_action(
    session: AsyncSession, identity: str, operation: str, record_id: UUID, *, actor_id: str
) -> None:
    match identity, operation:
        case (
            "user",
            "verify-email" | "promote-superuser" | "demote-superuser" | "deactivate" | "reactivate" | "soft-delete",
        ):
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


async def describe_support_target(
    session: AsyncSession, identity: str, record_id: UUID, *, operation: str, actor_id: str
) -> str:
    """Show the actual target before confirmation, without changing its state."""
    match identity:
        case "user":
            user = await crud.user.get(session, record_id)
            actor = await crud.user.get(session, UUID(actor_id))
            _authorize_user_action(actor, user, operation)
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


async def _locked_action_users(session: SAAsyncSession, record_id: UUID, actor_id: str) -> tuple[User, User]:
    users = {user.id: user for user in await crud.user.get_by_ids_for_update(session, [UUID(actor_id), record_id])}
    actor = users.get(UUID(actor_id))
    if actor is None:
        raise AccessDeniedException
    target = users.get(record_id)
    if target is None:
        raise ResourceNotFoundException(User, identifier=record_id)
    return actor, target


def _protect_account(actor: User, target: User, operation: str) -> None:
    if is_first_superuser(target):
        raise ValidationException("The first superuser cannot be deactivated, deleted, or demoted.")
    if target.id == actor.id:
        raise ValidationException(f"You cannot {operation} the account you are using.")


async def _deactivate_user(session: AsyncSession, target: User, *, soft_delete: bool = False) -> None:
    vaults = await crud.vault.get_by_user_id(db_session=session, user_id=target.id)
    await crud.game_state_crud.pause_many(session, [vault.id for vault in vaults])
    if soft_delete:
        target.soft_delete()
    target.is_active = False
    target.email_verification_token = None
    target.password_reset_token = None
    target.password_reset_expires = None


async def _update_user(session: AsyncSession, operation: str, record_id: UUID, actor_id: str) -> None:
    actor, target = await _locked_action_users(session, record_id, actor_id)
    _authorize_user_action(actor, target, operation)
    if operation in {"deactivate", "soft-delete", "demote-superuser"}:
        _protect_account(actor, target, operation)
    if operation in {"soft-delete", "deactivate"}:
        await _deactivate_user(session, target, soft_delete=operation == "soft-delete")
    elif operation == "reactivate":
        target.is_active = True
    elif operation in FIRST_SUPERUSER_OPERATIONS:
        target.is_superuser = operation == "promote-superuser"
    else:
        target.email_verified = True
        target.email_verification_token = None
    await session.commit()


async def create_user_account(session: AsyncSession, user_in: UserCreate, *, actor_id: UUID) -> User:
    users = await crud.user.get_by_ids_for_update(session, [actor_id])
    actor = next(iter(users), None)
    if actor is None or not crud.user.is_active(actor) or not actor.is_superuser:
        raise AccessDeniedException
    if user_in.is_superuser and not is_first_superuser(actor):
        raise AccessDeniedException("Only the first superuser can create administrator accounts.")
    if await crud.user.get_by_email(session, email=user_in.email):
        raise ResourceConflictException("The user with this username already exists in the system.")
    return await crud.user.create(session, obj_in=user_in)


async def update_user_account(session: AsyncSession, record_id: UUID, user_in: UserUpdate, *, actor_id: UUID) -> User:
    actor, target = await _locked_action_users(session, record_id, str(actor_id))
    updates = user_in.model_dump(exclude_unset=True)
    for flag in ("is_superuser", "is_active"):
        if flag in updates and not isinstance(updates[flag], bool):
            raise ValidationException(f"{flag} must be a boolean.")
    role_changed = "is_superuser" in updates and updates["is_superuser"] != target.is_superuser
    operation = (
        ("promote-superuser" if updates["is_superuser"] else "demote-superuser") if role_changed else "update-user"
    )
    _authorize_user_action(actor, target, operation)
    if role_changed and not updates["is_superuser"]:
        _protect_account(actor, target, "demote-superuser")
    if updates.get("is_active") is False:
        _protect_account(actor, target, "deactivate")
        await _deactivate_user(session, target)
    return await crud.user.update(session, id=target.id, obj_in=user_in)


async def authorize_profile_edit(session: SAAsyncSession, owner_id: UUID, *, actor_id: str) -> None:
    actor, target = await _locked_action_users(session, owner_id, actor_id)
    _authorize_user_action(actor, target, "edit-profile")
