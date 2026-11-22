"""Claim uniqueness, the derived bonus, and the death/recycling clearing rules."""

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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_death_clears_the_bonus_and_revival_keeps_it_cleared(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _finder(async_session, vault)
    await _award_strength(async_session, vault, dweller)
    await async_session.commit()

    await death_service.mark_as_dead(async_session, dweller, DeathCauseEnum.HEALTH)
    await async_session.refresh(dweller)
    assert dweller.collectible_bonus is None

    vault.bottle_caps = 999_999
    async_session.add(vault)
    await async_session.commit()
    user = await crud.user.get(async_session, vault.user_id)
    await death_service.revive_dweller(async_session, dweller.id, user)

    revived = await crud.dweller.get(async_session, dweller.id)
    assert revived.collectible_bonus is None


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_rolled_back_award_leaves_no_claim_or_bonus(async_session: AsyncSession, vault: Vault) -> None:
    """A failed transaction owner leaves neither the claim nor the derived bonus behind."""
    dweller = await _finder(async_session, vault)
    vault_id, dweller_id = vault.id, dweller.id

    await collectible_service.award(async_session, vault_id=vault_id, dweller=dweller, collectible_key="agility")
    await async_session.rollback()

    assert await collectible_crud.get_by_vault_and_key(async_session, vault_id, "agility") is None
    reloaded = await crud.dweller.get(async_session, dweller_id)
    assert reloaded.collectible_bonus is None
