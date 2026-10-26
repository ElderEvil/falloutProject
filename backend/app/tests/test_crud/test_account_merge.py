"""Focused coverage for the CRUD helpers the account-merge service calls."""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import NotificationType
from app.crud.chat_message import chat_message as chat_message_crud
from app.crud.llm_interaction import llm_interaction as llm_interaction_crud
from app.crud.notification import notification as notification_crud
from app.crud.user import build_user_model
from app.crud.user_profile import profile_crud
from app.models.chat_message import ChatMessage
from app.models.llm_interaction import LLMInteraction
from app.models.notification import Notification
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.models.vault import Vault
from app.tests.factory.vaults import random_vault_number
from app.tests.utils.utils import random_lower_string


async def _make_user(async_session: AsyncSession) -> User:
    user = build_user_model(
        username=f"u{random_lower_string(10)}",
        email=f"{random_lower_string(10)}@example.com",
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    return user


def _vault_number(*used: int) -> int:
    number = random_vault_number()
    while number in used:
        number = random_vault_number()
    return number


@pytest.mark.asyncio
async def test_resolve_identity_by_uuid_email_and_username(async_session: AsyncSession) -> None:
    user = await _make_user(async_session)

    assert (await crud.user.resolve_identity(async_session, str(user.id))).id == user.id
    assert (await crud.user.resolve_identity(async_session, str(user.email))).id == user.id
    assert (await crud.user.resolve_identity(async_session, user.username)).id == user.id
    assert await crud.user.resolve_identity(async_session, "missing-identity") is None


@pytest.mark.asyncio
async def test_resolve_identity_excludes_deleted_unless_requested(async_session: AsyncSession) -> None:
    user = await _make_user(async_session)
    user.soft_delete()
    await async_session.commit()

    assert await crud.user.resolve_identity(async_session, str(user.id)) is None
    resolved = await crud.user.resolve_identity(async_session, str(user.id), include_deleted=True)
    assert resolved is not None
    assert resolved.id == user.id


@pytest.mark.asyncio
async def test_lock_users_for_merge_locks_soft_deleted_source(async_session: AsyncSession) -> None:
    source = await _make_user(async_session)
    target = await _make_user(async_session)
    actor = await _make_user(async_session)
    source.soft_delete()
    await async_session.commit()

    locked = await crud.user.lock_users_for_merge(async_session, [target.id, source.id, actor.id, source.id])

    assert set(locked) == {source.id, target.id, actor.id}
    assert locked[source.id].is_deleted is True


@pytest.mark.asyncio
async def test_account_merge_create_stages_until_rollback(async_session: AsyncSession) -> None:
    source, target, actor = [await _make_user(async_session) for _ in range(3)]
    source_id = source.id

    audit = await crud.account_merge.create(
        async_session,
        source_user_id=source.id,
        target_user_id=target.id,
        actor_user_id=actor.id,
        source_username=source.username,
        source_email=str(source.email),
        target_username=target.username,
        target_email=str(target.email),
        reason="duplicate account",
        moved_counts={"vaults": 1},
        commit=False,
    )

    staged = await crud.account_merge.get_by_source(async_session, source_id)
    assert staged is not None
    assert staged.id == audit.id

    await async_session.rollback()
    assert await crud.account_merge.get_by_source(async_session, source_id) is None


@pytest.mark.asyncio
async def test_account_merge_create_commits_and_round_trips_counts(async_session: AsyncSession) -> None:
    source, target, actor = [await _make_user(async_session) for _ in range(3)]

    audit = await crud.account_merge.create(
        async_session,
        source_user_id=source.id,
        target_user_id=target.id,
        actor_user_id=actor.id,
        source_username=source.username,
        source_email=str(source.email),
        target_username=target.username,
        target_email=str(target.email),
        reason="duplicate account",
        moved_counts={"vaults": 2, "notifications": 5},
    )

    found = await crud.account_merge.get_by_source(async_session, source.id)
    assert found is not None
    await async_session.refresh(found)
    assert found.id == audit.id
    assert found.moved_counts == {"vaults": 2, "notifications": 5}
    assert found.created_at is not None


@pytest.mark.asyncio
async def test_vault_reassign_moves_soft_deleted_vaults(async_session: AsyncSession) -> None:
    source = await _make_user(async_session)
    target = await _make_user(async_session)
    active = Vault(user_id=source.id, number=_vault_number())
    deleted = Vault(user_id=source.id, number=_vault_number(active.number))
    deleted.soft_delete()
    async_session.add_all([active, deleted])
    await async_session.commit()

    assert await crud.vault.count_by_user(async_session, source.id) == 2
    assert sorted(await crud.vault.list_numbers_by_user(async_session, source.id)) == sorted(
        [active.number, deleted.number]
    )

    moved = await crud.vault.reassign_user(async_session, source.id, target.id, commit=False)
    await async_session.flush()

    assert moved == 2
    assert await crud.vault.count_by_user(async_session, source.id) == 0
    assert await crud.vault.count_by_user(async_session, target.id) == 2


@pytest.mark.asyncio
async def test_chat_reassign_updates_both_directions_and_counts_once(async_session: AsyncSession) -> None:
    source = await _make_user(async_session)
    target = await _make_user(async_session)
    other = await _make_user(async_session)
    vault = Vault(user_id=other.id, number=_vault_number())
    async_session.add(vault)
    await async_session.flush()

    messages = [
        ChatMessage(vault_id=vault.id, from_user_id=source.id, to_user_id=other.id, message_text="out"),
        ChatMessage(vault_id=vault.id, from_user_id=other.id, to_user_id=source.id, message_text="in"),
        ChatMessage(vault_id=vault.id, from_user_id=source.id, to_user_id=source.id, message_text="self"),
    ]
    async_session.add_all(messages)
    await async_session.commit()
    message_ids = [message.id for message in messages]
    source_id = source.id
    target_id = target.id
    other_id = other.id

    assert await chat_message_crud.count_by_user(async_session, source_id) == 3

    moved = await chat_message_crud.reassign_user(async_session, source_id, target_id, commit=False)
    await async_session.flush()
    async_session.expire_all()

    assert moved == 3
    assert await chat_message_crud.count_by_user(async_session, source_id) == 0
    assert await chat_message_crud.count_by_user(async_session, target_id) == 3
    rows = (await async_session.execute(select(ChatMessage).where(ChatMessage.id.in_(message_ids)))).scalars().all()
    assert {row.from_user_id for row in rows} == {target_id, other_id}
    assert {row.to_user_id for row in rows if row.to_user_id is not None} == {target_id, other_id}


@pytest.mark.asyncio
async def test_notification_llm_and_oauth_helpers_move_owned_rows(async_session: AsyncSession) -> None:
    source = await _make_user(async_session)
    target = await _make_user(async_session)
    async_session.add_all(
        [
            Notification(
                user_id=source.id,
                notification_type=NotificationType.LEVEL_UP,
                title="Level up",
                message="A dweller leveled up",
            ),
            LLMInteraction(parameters="p", response="r", usage="chat", user_id=source.id, total_tokens=12),
            OAuthAccount(provider="google", provider_user_id=random_lower_string(16), user_id=source.id),
        ]
    )
    await async_session.commit()

    assert await notification_crud.count_by_user(async_session, source.id) == 1
    assert await llm_interaction_crud.count_by_user(async_session, source.id) == 1
    assert await crud.oauth_account.count_by_user(async_session, source.id) == 1
    assert len(await crud.oauth_account.list_by_user(async_session, source.id)) == 1

    assert await notification_crud.reassign_user(async_session, source.id, target.id, commit=False) == 1
    assert await llm_interaction_crud.reassign_user(async_session, source.id, target.id, commit=False) == 1
    assert await crud.oauth_account.reassign_user(async_session, source.id, target.id, commit=False) == 1
    await async_session.flush()

    assert await notification_crud.count_by_user(async_session, target.id) == 1
    assert await llm_interaction_crud.count_by_user(async_session, target.id) == 1
    assert await crud.oauth_account.count_by_user(async_session, target.id) == 1


@pytest.mark.asyncio
async def test_profile_helpers_lock_and_reassign(async_session: AsyncSession) -> None:
    source = await _make_user(async_session)
    target = await _make_user(async_session)

    source_profile = await profile_crud.create_staged(async_session, source.id)
    await async_session.commit()

    locked = await profile_crud.lock_by_user_ids(async_session, [source.id, target.id])
    assert [profile.id for profile in locked] == [source_profile.id]

    moved = await profile_crud.reassign_user(async_session, source.id, target.id, commit=False)
    await async_session.flush()

    assert moved == 1
    assert await profile_crud.get_by_user_id(async_session, source.id) is None
    assert (await profile_crud.get_by_user_id(async_session, target.id)).id == source_profile.id


@pytest.mark.asyncio
async def test_profile_delete_for_user_only_removes_requested_profile(async_session: AsyncSession) -> None:
    survivor = await _make_user(async_session)
    discarded = await _make_user(async_session)
    survivor_profile = await profile_crud.create_staged(async_session, survivor.id)
    await profile_crud.create_staged(async_session, discarded.id)
    await async_session.commit()

    deleted = await profile_crud.delete_for_user(async_session, discarded.id, commit=True)

    assert deleted == 1
    assert await profile_crud.get_by_user_id(async_session, discarded.id) is None
    assert (await profile_crud.get_by_user_id(async_session, survivor.id)).id == survivor_profile.id
