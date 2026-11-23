import fakeredis.aioredis
import pytest
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import NotificationType
from app.crud.user import build_user_model
from app.crud.user_profile import profile_crud
from app.models.account_merge import AccountMerge
from app.models.chat_message import ChatMessage
from app.models.llm_interaction import LLMInteraction
from app.models.notification import Notification
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.models.vault import Vault
from app.services.account_merge_service import merge_users
from app.tests.factory.vaults import random_vault_number
from app.tests.utils.utils import random_lower_string
from app.utils.exceptions import (
    AccessDeniedException,
    ResourceConflictException,
    ResourceNotFoundException,
    ValidationException,
)

pytestmark = pytest.mark.asyncio


async def _make_user(
    session: AsyncSession,
    *,
    superuser: bool = False,
    first_superuser: bool = False,
    active: bool = True,
    password: str | None = None,
    with_profile: bool = True,
    email: str | None = None,
) -> User:
    suffix = random_lower_string(10)
    user = build_user_model(username=f"u{suffix}", email=email or f"{suffix}@example.com")
    user.is_superuser = superuser
    user.is_first_superuser = first_superuser
    user.is_active = active
    user.hashed_password = password
    session.add(user)
    await session.flush()
    if with_profile:
        await profile_crud.create_staged(session, user.id)
    await session.commit()
    return user


async def _trio(session: AsyncSession, *, source_password: str | None = None) -> tuple[User, User, User]:
    return (
        await _make_user(session, password=source_password),
        await _make_user(session),
        await _make_user(session, superuser=True),
    )


async def _fresh(session: AsyncSession, user_id) -> User:
    return await crud.user.get(session, user_id, include_deleted=True)


async def _audit_count(session: AsyncSession) -> int:
    return int((await session.execute(select(func.count()).select_from(AccountMerge))).scalar_one())


async def _merge(
    session, source_id, target_id, actor_id, *, reason: str = "duplicate", dry_run: bool = False, redis=None
):
    return await merge_users(
        session,
        str(source_id),
        str(target_id),
        actor=str(actor_id),
        reason=reason,
        dry_run=dry_run,
        redis_client=redis,
    )


async def _seed_owned_rows(session: AsyncSession, source: User, target: User) -> dict:
    source_profile = await profile_crud.get_by_user_id(session, source.id)
    target_profile = await profile_crud.get_by_user_id(session, target.id)
    assert source_profile is not None
    assert target_profile is not None
    source_profile.total_caps_earned, source_profile.total_dwellers_created = 10, 2
    target_profile.total_caps_earned, target_profile.total_dwellers_created = 5, 1

    vault = Vault(user_id=source.id, number=random_vault_number())
    deleted_vault = Vault(user_id=source.id, number=random_vault_number())
    deleted_vault.soft_delete()
    session.add_all(
        [
            vault,
            deleted_vault,
            Notification(
                user_id=source.id,
                notification_type=NotificationType.LEVEL_UP,
                title="Level up",
                message="A dweller leveled up",
            ),
            LLMInteraction(parameters="prompt", response="response", usage="chat", user_id=source.id, total_tokens=7),
            OAuthAccount(provider="google", provider_user_id=random_lower_string(16), user_id=source.id),
        ]
    )
    await session.flush()
    session.add_all(
        [
            ChatMessage(vault_id=vault.id, from_user_id=source.id, to_user_id=target.id, message_text="out"),
            ChatMessage(vault_id=vault.id, from_user_id=target.id, to_user_id=source.id, message_text="in"),
        ]
    )
    await session.commit()
    return {
        "vault": vault,
        "deleted_vault": deleted_vault,
        "source_profile": source_profile,
        "target_profile": target_profile,
    }


async def test_apply_moves_every_owned_row_and_tombstones_source(async_session: AsyncSession) -> None:
    source, target, actor = await _trio(async_session, source_password="source-hash")
    seeded = await _seed_owned_rows(async_session, source, target)
    source_id, target_id = source.id, target.id
    old_email, original_username = str(source.email), source.username
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(f"refresh_token:{source_id}", "source-token")
    await redis.set(f"refresh_token:{target_id}", "target-token")

    try:
        preview = await _merge(async_session, source_id, target_id, actor.id, redis=redis)
        assert await redis.get(f"refresh_token:{source_id}") is None
        assert await redis.get(f"refresh_token:{target_id}") == "target-token"
    finally:
        await redis.aclose()

    assert preview.applied is True
    assert preview.already_merged is False
    assert preview.audit_id is not None
    assert preview.moved_counts == {
        "vaults": 2,
        "vaults_soft_deleted": 1,
        "notifications": 1,
        "llm_interactions": 1,
        "chat_messages": 2,
        "conversations": 0,
        "oauth_links": 1,
        "profiles": 1,
    }

    fresh_source = await _fresh(async_session, source_id)
    fresh_target = await _fresh(async_session, target_id)
    assert (fresh_source.is_deleted, fresh_source.is_active, fresh_source.hashed_password) == (True, False, None)
    assert fresh_source.email != old_email
    assert fresh_source.email.startswith("merged-")
    assert fresh_source.username.startswith("merged_")
    assert fresh_source.username != original_username
    assert fresh_target.hashed_password == "source-hash"

    assert await crud.vault.count_by_user(async_session, source_id) == 0
    assert await crud.vault.count_by_user(async_session, target_id) == 2
    assert await crud.notification.count_by_user(async_session, source_id) == 0
    assert await crud.notification.count_by_user(async_session, target_id) == 1
    assert await crud.llm_interaction.count_by_user(async_session, source_id) == 0
    assert await crud.llm_interaction.count_by_user(async_session, target_id) == 1
    assert await crud.chat_message.count_by_user(async_session, source_id) == 0
    assert await crud.chat_message.count_by_user(async_session, target_id) == 2
    assert await crud.oauth_account.count_by_user(async_session, source_id) == 0
    assert await crud.oauth_account.count_by_user(async_session, target_id) == 1

    target_profile = await profile_crud.get_by_user_id(async_session, target_id)
    assert target_profile is not None
    assert (target_profile.total_caps_earned, target_profile.total_dwellers_created) == (15, 3)
    assert await profile_crud.get_by_user_id(async_session, source_id) is None

    assert await _audit_count(async_session) == 1
    audit = await crud.account_merge.get_by_source(async_session, source_id)
    assert audit is not None
    assert (audit.source_username, audit.source_email, audit.reason) == (original_username, old_email, "duplicate")


async def test_dry_run_reports_counts_conflicts_and_changes_nothing(async_session: AsyncSession) -> None:
    source, target, actor = await _trio(async_session)
    seeded = await _seed_owned_rows(async_session, source, target)
    async_session.add(Vault(user_id=target.id, number=seeded["vault"].number))
    await async_session.commit()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(f"refresh_token:{source.id}", "source-token")

    try:
        preview = await _merge(async_session, source.id, target.id, actor.id, dry_run=True, redis=redis)
        assert await redis.get(f"refresh_token:{source.id}") == "source-token"
    finally:
        await redis.aclose()

    assert preview.applied is False
    assert preview.already_merged is False
    assert preview.vault_numbers == sorted([seeded["vault"].number, seeded["deleted_vault"].number])
    assert preview.duplicate_vault_numbers == [seeded["vault"].number]
    assert preview.oauth_conflicts == []
    assert preview.tokens_this_month == {"source": 7, "target": 0}
    assert {key: preview.moved_counts[key] for key in ("vaults", "vaults_soft_deleted", "notifications")} == {
        "vaults": 2,
        "vaults_soft_deleted": 1,
        "notifications": 1,
    }
    assert preview.moved_counts["chat_messages"] == 2
    assert preview.moved_counts["oauth_links"] == 1

    assert (await _fresh(async_session, source.id)).is_deleted is False
    assert await _audit_count(async_session) == 0
    assert await crud.vault.count_by_user(async_session, source.id) == 2


async def test_apply_allows_duplicate_vault_numbers(async_session: AsyncSession) -> None:
    source, target, actor = await _trio(async_session)
    number = random_vault_number()
    async_session.add_all([Vault(user_id=source.id, number=number), Vault(user_id=target.id, number=number)])
    await async_session.commit()

    preview = await _merge(async_session, source.id, target.id, actor.id)

    assert preview.applied is True
    assert preview.duplicate_vault_numbers == [number]
    assert await crud.vault.count_by_user(async_session, source.id) == 0
    assert sorted(await crud.vault.list_numbers_by_user(async_session, target.id)) == [number, number]


async def test_rejects_oauth_provider_conflict(async_session: AsyncSession) -> None:
    source, target, actor = await _trio(async_session)
    source_id = source.id
    async_session.add_all(
        [
            OAuthAccount(provider="google", provider_user_id=random_lower_string(16), user_id=source_id),
            OAuthAccount(provider="google", provider_user_id=random_lower_string(16), user_id=target.id),
        ]
    )
    await async_session.commit()

    assert (await _merge(async_session, source.id, target.id, actor.id, dry_run=True)).oauth_conflicts == ["google"]

    with pytest.raises(ResourceConflictException):
        await _merge(async_session, source.id, target.id, actor.id)

    assert (await _fresh(async_session, source_id)).is_deleted is False
    assert await _audit_count(async_session) == 0


async def test_idempotent_retry_and_different_target_conflict(async_session: AsyncSession) -> None:
    source, target, actor = await _trio(async_session)
    other_target = await _make_user(async_session)
    await _seed_owned_rows(async_session, source, target)

    first = await _merge(async_session, source.id, target.id, actor.id)
    second = await _merge(async_session, source.id, target.id, actor.id, reason="retry")

    assert first.applied is True
    assert second.already_merged is True
    assert second.applied is False
    assert second.audit_id == first.audit_id
    assert await _audit_count(async_session) == 1

    with pytest.raises(ResourceConflictException):
        await _merge(async_session, source.id, other_target.id, actor.id, reason="wrong target")


async def test_old_email_reused_by_new_user_cannot_retry_merge(async_session: AsyncSession) -> None:
    source, target, actor = await _trio(async_session)
    old_email = str(source.email)
    await _seed_owned_rows(async_session, source, target)
    await _merge(async_session, source.id, target.id, actor.id)
    await _make_user(async_session, email=old_email)

    with pytest.raises(ResourceConflictException, match="source UUID"):
        await _merge(async_session, old_email, target.id, actor.id, reason="retry by old email")


async def test_source_password_is_moved_only_when_target_has_none(async_session: AsyncSession) -> None:
    source, target, actor = await _trio(async_session, source_password="source-hash")
    target.hashed_password = "target-hash"
    await async_session.commit()

    await _merge(async_session, source.id, target.id, actor.id)

    assert (await _fresh(async_session, source.id)).hashed_password is None
    assert (await _fresh(async_session, target.id)).hashed_password == "target-hash"


async def test_target_profile_missing_is_reassigned_from_source(async_session: AsyncSession) -> None:
    source, target, actor = await _trio(async_session)
    source_profile = await profile_crud.get_by_user_id(async_session, source.id)
    assert source_profile is not None
    source_profile.total_caps_earned = 11
    await profile_crud.delete_for_user(async_session, target.id, commit=True)

    preview = await _merge(async_session, source.id, target.id, actor.id)

    target_profile = await profile_crud.get_by_user_id(async_session, target.id)
    assert target_profile is not None
    assert (target_profile.id, target_profile.total_caps_earned) == (source_profile.id, 11)
    assert await profile_crud.get_by_user_id(async_session, source.id) is None
    assert preview.moved_counts["profiles"] == 1


async def test_both_profiles_missing_creates_target_profile(async_session: AsyncSession) -> None:
    source, target, actor = await _trio(async_session)
    await profile_crud.delete_for_user(async_session, source.id, commit=True)
    await profile_crud.delete_for_user(async_session, target.id, commit=True)

    preview = await _merge(async_session, source.id, target.id, actor.id)

    assert await profile_crud.get_by_user_id(async_session, target.id) is not None
    assert await profile_crud.get_by_user_id(async_session, source.id) is None
    assert preview.moved_counts["profiles"] == 0


async def test_late_audit_failure_rolls_back_everything(async_session: AsyncSession, monkeypatch) -> None:
    source, target, actor = await _trio(async_session)
    await _seed_owned_rows(async_session, source, target)
    source_id, target_id, source_username = source.id, target.id, source.username
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(f"refresh_token:{source_id}", "source-token")
    await redis.set(f"refresh_token:{target_id}", "target-token")

    async def fail_create(*args, **kwargs):
        raise RuntimeError("late audit failure")

    monkeypatch.setattr(crud.account_merge, "create", fail_create)
    try:
        with pytest.raises(RuntimeError, match="late audit failure"):
            await _merge(async_session, source_id, target_id, actor.id, redis=redis)
        assert await redis.get(f"refresh_token:{source_id}") == "source-token"
        assert await redis.get(f"refresh_token:{target_id}") == "target-token"
    finally:
        await redis.aclose()

    fresh_source = await _fresh(async_session, source_id)
    assert (fresh_source.is_deleted, fresh_source.is_active, fresh_source.username) == (False, True, source_username)
    assert await crud.vault.count_by_user(async_session, source_id) == 2
    assert await crud.notification.count_by_user(async_session, source_id) == 1
    assert await crud.llm_interaction.count_by_user(async_session, source_id) == 1
    assert await crud.chat_message.count_by_user(async_session, source_id) == 2
    assert await crud.oauth_account.count_by_user(async_session, source_id) == 1
    assert await profile_crud.get_by_user_id(async_session, source_id) is not None
    assert await _audit_count(async_session) == 0


async def test_rejects_self_merge_non_superuser_actor_and_inactive_target(async_session: AsyncSession) -> None:
    source, target, actor = await _trio(async_session)

    with pytest.raises(ValidationException, match="different"):
        await _merge(async_session, source.id, source.id, actor.id)

    normal_actor = await _make_user(async_session)
    with pytest.raises(AccessDeniedException):
        await _merge(async_session, source.id, target.id, normal_actor.id)

    target.is_active = False
    await async_session.commit()
    with pytest.raises(ValidationException, match="inactive or deleted"):
        await _merge(async_session, source.id, target.id, actor.id)


async def test_rejects_superuser_and_first_superuser_accounts(async_session: AsyncSession) -> None:
    actor = await _make_user(async_session, superuser=True)
    source = await _make_user(async_session, superuser=True)
    target = await _make_user(async_session)

    with pytest.raises(ValidationException, match="Superuser"):
        await _merge(async_session, source.id, target.id, actor.id)

    first = await _make_user(async_session, first_superuser=True)
    with pytest.raises(ValidationException, match="first superuser"):
        await _merge(async_session, first.id, target.id, actor.id)


async def test_rejects_actor_membership_empty_reason_and_deleted_target(async_session: AsyncSession) -> None:
    source, target, actor = await _trio(async_session)

    with pytest.raises(ValidationException, match="actor cannot"):
        await _merge(async_session, source.id, target.id, source.id)

    with pytest.raises(ValidationException, match="reason"):
        await _merge(async_session, source.id, target.id, actor.id, reason="  ")

    target.soft_delete()
    await async_session.commit()
    with pytest.raises(ResourceNotFoundException):
        await _merge(async_session, source.id, target.id, actor.id)


async def test_allows_already_soft_deleted_source(async_session: AsyncSession) -> None:
    source, target, actor = await _trio(async_session)
    source.soft_delete()
    await async_session.commit()

    preview = await _merge(async_session, source.id, target.id, actor.id)

    assert preview.applied is True
    assert (await _fresh(async_session, source.id)).is_deleted is True
    assert await _audit_count(async_session) == 1
