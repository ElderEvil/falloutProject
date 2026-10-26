"""Superuser account merge orchestration.

One public entry point owns the transaction: lock the participants, move every
owned row, tombstone the source and write the audit row, then commit once.
External refresh-token invalidation happens after commit.
"""

import logging
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core import security
from app.crud.user_profile import profile_crud
from app.models.account_merge import AccountMerge
from app.models.user import User
from app.models.user_profile import UserProfile
from app.utils.exceptions import (
    AccessDeniedException,
    ResourceConflictException,
    ResourceNotFoundException,
    ValidationException,
)

logger = logging.getLogger(__name__)

PROFILE_COUNTER_FIELDS = (
    "total_dwellers_created",
    "total_caps_earned",
    "total_explorations",
    "total_rooms_built",
    "total_incidents",
    "total_incidents_won",
    "total_incidents_lost",
    "total_dwellers_born",
    "total_dwellers_died",
    "deaths_by_health",
    "deaths_by_radiation",
    "deaths_by_incident",
    "deaths_by_exploration",
    "deaths_by_combat",
)


@dataclass(frozen=True)
class MergePreview:
    source_id: UUID
    source_username: str
    source_email: str | None
    target_id: UUID
    target_username: str
    target_email: str | None
    moved_counts: dict[str, int]
    vault_numbers: list[int]
    duplicate_vault_numbers: list[int]
    oauth_conflicts: list[str]
    tokens_this_month: dict[str, int]
    result_email: str | None
    result_username: str
    already_merged: bool = False
    applied: bool = False
    audit_id: UUID | None = None
    token_invalidation_failed: bool = False


def _email(value: object) -> str | None:
    return str(value) if value else None


def _looks_like_uuid(identity: str) -> bool:
    try:
        UUID(identity)
    except ValueError:
        return False
    return True


async def _resolve(db_session: AsyncSession, identity: str, *, include_deleted: bool) -> User | None:
    return await crud.user.resolve_identity(db_session, identity, include_deleted=include_deleted)


def _authorize(actor: User, source: User, target: User, reason: str) -> None:
    if not reason.strip():
        raise ValidationException("A merge reason is required.")
    if source.id == target.id:
        raise ValidationException("Source and target must be different accounts.")
    if actor.id in {source.id, target.id}:
        raise ValidationException("The actor cannot be the source or target account.")
    if not crud.user.is_active(actor) or not actor.is_superuser:
        raise AccessDeniedException
    if source.is_superuser or target.is_superuser:
        raise ValidationException("Superuser accounts cannot be merged.")
    if source.is_first_superuser or target.is_first_superuser:
        raise ValidationException("The first superuser cannot be merged.")
    if target.is_deleted or not target.is_active:
        raise ValidationException("The target account is inactive or deleted.")


async def _reject_reused_source_identity(db_session: AsyncSession, identity: str, source: User) -> None:
    """Old email/username may now belong to a different user after tombstoning."""
    if _looks_like_uuid(identity):
        return
    if "@" in identity:
        audit = await crud.account_merge.get_by_source_email(db_session, identity)
    else:
        audit = await crud.account_merge.get_by_source_username(db_session, identity)
    if audit is not None and audit.source_user_id != source.id:
        raise ResourceConflictException(
            "That identity belonged to an account that was already merged; retry with the source UUID."
        )


def _preview_from_audit(audit: AccountMerge) -> MergePreview:
    return MergePreview(
        source_id=audit.source_user_id,
        source_username=audit.source_username,
        source_email=audit.source_email,
        target_id=audit.target_user_id,
        target_username=audit.target_username,
        target_email=audit.target_email,
        moved_counts=dict(audit.moved_counts or {}),
        vault_numbers=[],
        duplicate_vault_numbers=[],
        oauth_conflicts=[],
        tokens_this_month={},
        result_email=audit.target_email,
        result_username=audit.target_username,
        already_merged=True,
        audit_id=audit.id,
    )


async def _build_preview(
    db_session: AsyncSession,
    source: User,
    target: User,
    *,
    source_profile: UserProfile | None,
) -> MergePreview:
    source_vault_numbers = await crud.vault.list_numbers_by_user(db_session, source.id)
    target_vault_numbers = await crud.vault.list_numbers_by_user(db_session, target.id)
    source_vaults = len(source_vault_numbers)
    active_source_vaults = await crud.vault.count_by_user(db_session, source.id, include_deleted=False)
    source_links = await crud.oauth_account.list_by_user(db_session, source.id)
    target_links = await crud.oauth_account.list_by_user(db_session, target.id)
    source_providers = {link.provider for link in source_links}
    target_providers = {link.provider for link in target_links}
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    moved_counts = {
        "vaults": source_vaults,
        "vaults_soft_deleted": source_vaults - active_source_vaults,
        "notifications": await crud.notification.count_by_user(db_session, source.id),
        "llm_interactions": await crud.llm_interaction.count_by_user(db_session, source.id),
        "chat_messages": await crud.chat_message.count_by_user(db_session, source.id),
        "oauth_links": len(source_links),
        "profiles": 1 if source_profile else 0,
    }

    return MergePreview(
        source_id=source.id,
        source_username=source.username,
        source_email=_email(source.email),
        target_id=target.id,
        target_username=target.username,
        target_email=_email(target.email),
        moved_counts=moved_counts,
        vault_numbers=source_vault_numbers,
        # Vault numbers are intentionally non-unique in v1 (#1198); report collisions, do not renumber.
        duplicate_vault_numbers=sorted(set(source_vault_numbers) & set(target_vault_numbers)),
        oauth_conflicts=sorted(source_providers & target_providers),
        tokens_this_month={
            "source": await crud.llm_interaction.total_tokens_since(db_session, source.id, month_start),
            "target": await crud.llm_interaction.total_tokens_since(db_session, target.id, month_start),
        },
        result_email=_email(target.email),
        result_username=target.username,
    )


async def _existing_audit(db_session: AsyncSession, source_id: UUID, target_id: UUID) -> MergePreview | None:
    audit = await crud.account_merge.get_by_source(db_session, source_id)
    if audit is None:
        return None
    if audit.target_user_id != target_id:
        raise ResourceConflictException(f"Source account was already merged into {audit.target_user_id}.")
    return _preview_from_audit(audit)


def _tombstone(source: User) -> None:
    source_id = source.id
    source.email = f"merged-{source_id.hex}@account-merge.invalid"
    source.username = f"merged_{source_id.hex[:24]}"
    source.is_active = False
    source.email_verified = False
    source.email_verification_token = None
    source.password_reset_token = None
    source.password_reset_expires = None
    source.hashed_password = None
    source.is_superuser = False
    source.is_first_superuser = False
    source.soft_delete()


def _locked_users_or_raise(
    locked: dict[UUID, User], source_id: UUID, target_id: UUID, actor_id: UUID
) -> tuple[User, User, User]:
    source_user = locked.get(source_id)
    target_user = locked.get(target_id)
    actor_user = locked.get(actor_id)
    if source_user is None:
        raise ResourceNotFoundException(User, source_id)
    if target_user is None:
        raise ResourceNotFoundException(User, target_id)
    if actor_user is None:
        raise AccessDeniedException
    return source_user, target_user, actor_user


def _reject_oauth_conflicts(preview: MergePreview) -> None:
    if not preview.oauth_conflicts:
        return
    providers = ", ".join(preview.oauth_conflicts)
    raise ResourceConflictException(f"Both accounts are linked to {providers}; unlink one before merging.")


async def _merge_profile(
    db_session: AsyncSession,
    source_profile: UserProfile | None,
    target_profile: UserProfile | None,
    *,
    source_id: UUID,
    target_id: UUID,
) -> int:
    if source_profile is None:
        if target_profile is None:
            await profile_crud.create_staged(db_session, target_id)
        return 0
    if target_profile is None:
        return await profile_crud.reassign_user(db_session, source_id, target_id, commit=False)
    for field in PROFILE_COUNTER_FIELDS:
        setattr(target_profile, field, getattr(target_profile, field) + getattr(source_profile, field))
    return await profile_crud.delete_for_user(db_session, source_id, commit=False)


async def merge_users(
    db_session: AsyncSession,
    source: str,
    target: str,
    *,
    actor: str,
    reason: str,
    dry_run: bool = True,
    redis_client: Redis | None = None,
) -> MergePreview:
    """Preview or apply a one-way merge of ``source`` into ``target``.

    The public entry point owns the single commit. Source refresh tokens are
    invalidated after commit; the surviving target session stays valid.
    """
    source_user = await _resolve(db_session, source, include_deleted=True)
    if source_user is None:
        raise ResourceNotFoundException(User, source)
    target_user = await _resolve(db_session, target, include_deleted=False)
    if target_user is None:
        raise ResourceNotFoundException(User, target)
    actor_user = await _resolve(db_session, actor, include_deleted=False)
    if actor_user is None:
        raise AccessDeniedException

    _authorize(actor_user, source_user, target_user, reason)
    await _reject_reused_source_identity(db_session, source, source_user)

    existing = await _existing_audit(db_session, source_user.id, target_user.id)
    if existing is not None:
        return existing

    if dry_run:
        source_profile = await profile_crud.get_by_user_id(db_session, source_user.id)
        return await _build_preview(
            db_session,
            source_user,
            target_user,
            source_profile=source_profile,
        )

    source_id = source_user.id
    target_id = target_user.id
    try:
        actor_id = actor_user.id
        locked = await crud.user.lock_users_for_merge(db_session, [actor_id, source_id, target_id])
        source_user, target_user, actor_user = _locked_users_or_raise(locked, source_id, target_id, actor_id)
        _authorize(actor_user, source_user, target_user, reason)

        existing = await _existing_audit(db_session, source_id, target_id)
        if existing is not None:
            await db_session.rollback()
            return existing

        profiles = await profile_crud.lock_by_user_ids(db_session, [source_id, target_id])
        profiles_by_user = {profile.user_id: profile for profile in profiles}
        source_profile = profiles_by_user.get(source_id)
        target_profile = profiles_by_user.get(target_id)

        preview = await _build_preview(
            db_session,
            source_user,
            target_user,
            source_profile=source_profile,
        )
        _reject_oauth_conflicts(preview)

        oauth_moved = await crud.oauth_account.reassign_user(db_session, source_id, target_id, commit=False)
        vault_moved = await crud.vault.reassign_user(db_session, source_id, target_id, commit=False)
        notification_moved = await crud.notification.reassign_user(db_session, source_id, target_id, commit=False)
        llm_moved = await crud.llm_interaction.reassign_user(db_session, source_id, target_id, commit=False)
        chat_moved = await crud.chat_message.reassign_user(db_session, source_id, target_id, commit=False)
        profile_moved = await _merge_profile(
            db_session,
            source_profile,
            target_profile,
            source_id=source_id,
            target_id=target_id,
        )

        if target_user.hashed_password is None and source_user.hashed_password is not None:
            target_user.hashed_password = source_user.hashed_password

        source_username = source_user.username
        source_email = _email(source_user.email)
        target_username = target_user.username
        target_email = _email(target_user.email)
        _tombstone(source_user)

        moved_counts = {
            "vaults": vault_moved,
            "vaults_soft_deleted": preview.moved_counts["vaults_soft_deleted"],
            "notifications": notification_moved,
            "llm_interactions": llm_moved,
            "chat_messages": chat_moved,
            "oauth_links": oauth_moved,
            "profiles": profile_moved,
        }
        await db_session.flush()
        audit = await crud.account_merge.create(
            db_session,
            source_user_id=source_id,
            target_user_id=target_id,
            actor_user_id=actor_user.id,
            source_username=source_username,
            source_email=source_email,
            target_username=target_username,
            target_email=target_email,
            reason=reason.strip(),
            moved_counts=moved_counts,
            commit=False,
        )
        await db_session.flush()
        await db_session.commit()
    except IntegrityError as exc:
        await db_session.rollback()
        existing = await crud.account_merge.get_by_source(db_session, source_id)
        if existing is not None and existing.target_user_id == target_id:
            return _preview_from_audit(existing)
        raise ResourceConflictException("Account merge conflicted with another operation.") from exc
    except Exception:
        await db_session.rollback()
        raise

    invalidation_failed = False
    if redis_client is not None:
        try:
            await security.invalidate_refresh_token(str(source_id), redis_client)
        except Exception:
            logger.warning("Failed to invalidate source refresh token after account merge", exc_info=True)
            invalidation_failed = True

    return replace(
        preview,
        moved_counts=moved_counts,
        applied=True,
        audit_id=audit.id,
        token_invalidation_failed=invalidation_failed,
    )
