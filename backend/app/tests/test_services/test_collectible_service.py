from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DeathCauseEnum
from app.core.game_config import game_config
from app.crud.collectible import collectible_crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.options.identity_modifiers import effective_stat
from app.schemas.dweller import DwellerCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.collectible_service import collectible_service
from app.services.dweller_recycling_service import dweller_recycling_service
from app.services.family.death_service import death_service
from app.services.notification_service import notification_service
from app.tests.factory.dwellers import create_fake_dweller
from app.tests.factory.vaults import create_fake_vault


async def _finder(async_session: AsyncSession, vault: Vault, *, luck: int = 5) -> Dweller:
    data = create_fake_dweller()
    data.update(
        {"first_name": "Finder", "last_name": "Dweller", "strength": 5, "luck": luck, "health": 100, "max_health": 100}
    )
    return await crud.dweller.create(db_session=async_session, obj_in=DwellerCreate(**data, vault_id=vault.id))


async def _award_strength(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    assert await collectible_service.award(
        async_session, vault_id=vault.id, dweller=dweller, collectible_key="strength"
    )


async def test_award_claims_once_and_applies_the_bonus(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _finder(async_session, vault)
    base = effective_stat(dweller, "strength")
    await _award_strength(async_session, vault, dweller)
    assert dweller.collectible_bonus == {"strength": 1}
    assert effective_stat(dweller, "strength") == base + 1
    assert (
        await collectible_service.award(async_session, vault_id=vault.id, dweller=dweller, collectible_key="strength")
        is False
    )
    assert dweller.collectible_bonus == {"strength": 1}


async def test_a_comic_grants_its_own_stat_once_per_vault(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _finder(async_session, vault)
    base = effective_stat(dweller, "luck")
    assert await collectible_service.award(
        async_session, vault_id=vault.id, dweller=dweller, collectible_key="astounding_tales"
    )
    assert dweller.collectible_bonus == {"luck": 1}
    assert effective_stat(dweller, "luck") == base + 1
    assert (
        await collectible_service.award(
            async_session, vault_id=vault.id, dweller=dweller, collectible_key="astounding_tales"
        )
        is False
    )
    assert dweller.collectible_bonus == {"luck": 1}


async def test_death_clears_the_bonus_and_revival_keeps_it_cleared(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _finder(async_session, vault)
    await _award_strength(async_session, vault, dweller)
    await async_session.commit()
    await death_service.mark_as_dead(async_session, dweller, DeathCauseEnum.HEALTH)
    await async_session.refresh(dweller)
    assert dweller.collectible_bonus is None
    claim = await collectible_crud.get_by_vault_and_key(async_session, vault.id, "strength")
    assert claim is not None
    # The vault keeps the claim; the finder's copy must stop promising the bonus.
    assert claim.bonus_live is False
    [read] = await collectible_service.list_for_dweller(async_session, dweller=dweller)
    assert read.amount == 0
    vault.bottle_caps = 999_999
    async_session.add(vault)
    await async_session.commit()
    user = await crud.user.get(async_session, vault.user_id)
    await death_service.revive_dweller(async_session, dweller.id, user)
    revived = await crud.dweller.get(async_session, dweller.id)
    assert revived.collectible_bonus is None
    claim = await collectible_crud.get_by_vault_and_key(async_session, vault.id, "strength")
    assert claim is not None
    assert claim.bonus_live is False


async def test_a_failed_death_leaves_the_claim_and_bonus_live(
    async_session: AsyncSession, vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The revoke shares the death transaction, so a late failure must not strand a dead claim."""
    vault_id = vault.id
    dweller = await _finder(async_session, vault)
    await _award_strength(async_session, vault, dweller)
    await async_session.commit()

    async def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("notification exploded")

    monkeypatch.setattr(notification_service, "notify_owner", explode)
    with pytest.raises(RuntimeError, match="notification exploded"):
        await death_service.mark_as_dead(async_session, dweller, DeathCauseEnum.HEALTH)

    claim = await collectible_crud.get_by_vault_and_key(async_session, vault_id, "strength")
    assert claim is not None
    assert claim.bonus_live is True
    await async_session.refresh(dweller)
    assert dweller.collectible_bonus == {"strength": 1}
    assert not dweller.is_dead


async def test_cross_vault_recycling_drops_the_bonus_even_without_stat_reset(
    async_session: AsyncSession, vault: Vault
) -> None:
    dweller = await _finder(async_session, vault)
    await _award_strength(async_session, vault, dweller)
    await crud.dweller.soft_delete(async_session, dweller.id)
    other_vault = await crud.vault.create(
        db_session=async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=vault.user_id),
    )
    recycled = await dweller_recycling_service.recycle_dweller_for_vault(
        async_session, dweller.id, other_vault.id, reset_stats=False
    )
    assert recycled.collectible_bonus is None
    claim = await collectible_crud.get_by_vault_and_key(async_session, vault.id, "strength")
    assert claim is not None
    assert claim.bonus_live is False


async def test_a_revoked_claim_stays_zero_after_a_new_bonus_of_the_same_stat(
    async_session: AsyncSession, vault: Vault
) -> None:
    """A same-vault re-recruit can earn a new bonus; the lost claim must not ride along with it."""
    dweller = await _finder(async_session, vault)
    await _award_strength(async_session, vault, dweller)
    await collectible_crud.revoke_finder_bonus(async_session, dweller_id=dweller.id)
    dweller.collectible_bonus = {"strength": 1}
    async_session.add(dweller)
    await async_session.commit()

    [read] = await collectible_service.list_for_dweller(async_session, dweller=dweller)
    assert read.amount == 0


async def test_a_legacy_claim_reads_zero_once_its_live_bonus_is_gone(async_session: AsyncSession, vault: Vault) -> None:
    """Claims written before the flag existed default to live; the live map still keeps them honest."""
    dweller = await _finder(async_session, vault)
    await _award_strength(async_session, vault, dweller)
    dweller.collectible_bonus = None
    async_session.add(dweller)
    await async_session.commit()

    [read] = await collectible_service.list_for_dweller(async_session, dweller=dweller)
    assert read.amount == 0


async def test_a_revoke_leaves_another_finders_claim_live(async_session: AsyncSession, vault: Vault) -> None:
    """Revoking one dweller must not touch the vault's other claims."""
    doomed = await _finder(async_session, vault)
    bystander = await _finder(async_session, vault)
    await _award_strength(async_session, vault, doomed)
    assert await collectible_service.award(
        async_session, vault_id=vault.id, dweller=bystander, collectible_key="perception"
    )

    await collectible_crud.revoke_finder_bonus(async_session, dweller_id=doomed.id)

    claim = await collectible_crud.get_by_vault_and_key(async_session, vault.id, "perception")
    assert claim is not None
    assert claim.bonus_live is True
    [read] = await collectible_service.list_for_dweller(async_session, dweller=bystander)
    assert read.amount == 1


async def test_a_failed_recycle_keeps_the_claim_and_bonus_live(
    async_session: AsyncSession, vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recycling composes the revoke with the bonus clear; a late failure restores both."""
    vault_id = vault.id
    dweller = await _finder(async_session, vault)
    dweller_id = dweller.id
    await _award_strength(async_session, vault, dweller)
    await crud.dweller.soft_delete(async_session, dweller_id)
    other_vault = await crud.vault.create(
        db_session=async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=vault.user_id),
    )
    target_vault_id = other_vault.id

    real_commit = async_session.commit
    calls = {"count": 0}

    async def explode_once() -> None:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("commit exploded")
        await real_commit()

    monkeypatch.setattr(async_session, "commit", explode_once)
    with pytest.raises(RuntimeError, match="commit exploded"):
        await dweller_recycling_service.recycle_dweller_for_vault(
            async_session, dweller_id, target_vault_id, reset_stats=False
        )

    await async_session.rollback()
    claim = await collectible_crud.get_by_vault_and_key(async_session, vault_id, "strength")
    assert claim is not None
    assert claim.bonus_live is True
    restored = await crud.dweller.get(async_session, dweller_id, include_deleted=True)
    await async_session.refresh(restored)
    assert restored.collectible_bonus == {"strength": 1}
    assert restored.vault_id == vault_id


async def test_site_award_goes_to_the_luckiest_survivor_once(
    async_session: AsyncSession, vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(game_config.features, "collectibles", True)
    unlucky = await _finder(async_session, vault, luck=3)
    lucky = await _finder(async_session, vault, luck=9)
    await async_session.commit()
    location = SimpleNamespace(id=uuid4(), name="Poseidon Energy")
    exploration = SimpleNamespace(vault_id=vault.id)
    payload = await collectible_service.award_site_collectible(
        async_session, exploration=exploration, location=location, members=[unlucky, lucky]
    )
    assert payload is not None
    assert payload.dweller_id == lucky.id
    claim = await collectible_crud.get_by_vault_and_key(async_session, vault.id, "strength")
    assert claim is not None
    assert claim.finder_dweller_id == lucky.id
    assert lucky.collectible_bonus == {"strength": 1}
    assert unlucky.collectible_bonus is None
    assert (
        await collectible_service.award_site_collectible(
            async_session, exploration=exploration, location=location, members=[unlucky, lucky]
        )
        is None
    )


async def test_site_award_is_inert_while_the_feature_flag_is_off(
    async_session: AsyncSession, vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(game_config.features, "collectibles", False)
    finder = await _finder(async_session, vault)
    location = SimpleNamespace(id=uuid4(), name="Poseidon Energy")
    payload = await collectible_service.award_site_collectible(
        async_session, exploration=SimpleNamespace(vault_id=vault.id), location=location, members=[finder]
    )
    assert payload is None
    assert await collectible_crud.get_by_vault_and_key(async_session, vault.id, "strength") is None


async def test_a_lost_claim_race_returns_false_without_touching_the_bonus(
    async_session: AsyncSession, vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The unique constraint, not the pre-check, decides a claim: a stale read must not raise.
    The pre-check can read an empty table while a concurrent award is committing. Losing that
    race has to cost the award, never the caller's transaction — the dispatch would roll back.
    """

    async def _stale_read(*args: object, **kwargs: object) -> None:
        return None

    dweller = await _finder(async_session, vault)
    await _award_strength(async_session, vault, dweller)
    await async_session.commit()
    monkeypatch.setattr(collectible_crud, "get_by_vault_and_key", _stale_read)
    assert (
        await collectible_service.award(async_session, vault_id=vault.id, dweller=dweller, collectible_key="strength")
        is False
    )
    await async_session.refresh(dweller)
    assert dweller.collectible_bonus == {"strength": 1}


async def test_rolled_back_award_leaves_no_claim_or_bonus(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _finder(async_session, vault)
    vault_id, dweller_id = vault.id, dweller.id
    await collectible_service.award(async_session, vault_id=vault_id, dweller=dweller, collectible_key="agility")
    await async_session.rollback()
    assert await collectible_crud.get_by_vault_and_key(async_session, vault_id, "agility") is None
    reloaded = await crud.dweller.get(async_session, dweller_id)
    assert reloaded.collectible_bonus is None
