"""Completed-set bonuses: derived from claims, gated by the flag, and paid exactly once.

Sets are read, never stored: completion is recomputed from ``vaultcollectible`` on every read, so
there is no counter to drift and no migration. The production case lives beside the resource
manager tests; this file covers the set semantics and the loot payout.
"""

from __future__ import annotations

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.game_config import game_config
from app.models.collectible import VaultCollectible
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services.collectible_service import collectible_service
from app.services.exploration.rewards_service import rewards_service
from app.services.exploration_service import exploration_service
from app.tests.factory.dwellers import create_fake_dweller
from app.utils.collectibles import EXPEDITION_LOOT_PCT, PRODUCTION_PCT

COMICS = ("grognak_barbarian", "astounding_tales", "silver_shroud")
BOBBLEHEADS = ("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck")


async def _finder(async_session: AsyncSession, vault: Vault) -> Dweller:
    data = create_fake_dweller()
    data.update({"first_name": "Collector", "last_name": "Dweller", "health": 100, "max_health": 100})
    return await crud.dweller.create(db_session=async_session, obj_in=DwellerCreate(**data, vault_id=vault.id))


async def _hold(async_session: AsyncSession, vault: Vault, keys: tuple[str, ...]) -> Dweller:
    finder = await _finder(async_session, vault)
    for key in keys:
        awarded = await collectible_service.award(async_session, vault_id=vault.id, dweller=finder, collectible_key=key)
        if not awarded:
            raise RuntimeError(f"{key} was already claimed")
    return finder


async def _multiplier(async_session: AsyncSession, vault: Vault, bonus_type: str) -> float:
    return await collectible_service.bonus_multiplier(async_session, vault_id=vault.id, bonus_type=bonus_type)


async def test_two_of_three_comics_pay_nothing(
    async_session: AsyncSession, vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(game_config.features, "collectibles", True)
    await _hold(async_session, vault, COMICS[:2])

    assert await _multiplier(async_session, vault, EXPEDITION_LOOT_PCT) == 1.0


async def test_three_comics_pay_the_loot_bonus_once(
    async_session: AsyncSession, vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(game_config.features, "collectibles", True)
    await _hold(async_session, vault, COMICS)

    assert await _multiplier(async_session, vault, EXPEDITION_LOOT_PCT) == pytest.approx(1.10)


async def test_the_bobblehead_cabinet_pays_production_and_comics_do_not(
    async_session: AsyncSession, vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each set pays only its own bonus type; the two never leak into one another."""
    monkeypatch.setattr(game_config.features, "collectibles", True)
    await _hold(async_session, vault, BOBBLEHEADS)

    assert await _multiplier(async_session, vault, PRODUCTION_PCT) == pytest.approx(1.05)
    assert await _multiplier(async_session, vault, EXPEDITION_LOOT_PCT) == 1.0


async def test_the_flag_off_pays_nothing_at_a_full_set(
    async_session: AsyncSession, vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(game_config.features, "collectibles", False)
    await _hold(async_session, vault, COMICS)

    assert await _multiplier(async_session, vault, EXPEDITION_LOOT_PCT) == 1.0
    progress = await collectible_service.set_progress(async_session, vault_id=vault.id)
    assert {row.set: row.active for row in progress} == {"comics": False, "bobbleheads": False, "magazines": False}


async def test_a_claim_whose_finder_is_gone_still_counts(
    async_session: AsyncSession, vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Progress reads claims, never the finder join: ON DELETE SET NULL must not un-complete a set.

    SQLite in the test harness does not enforce the FK, so the null is written directly — the
    same row shape the production database produces when the finder is deleted.
    """
    monkeypatch.setattr(game_config.features, "collectibles", True)
    await _hold(async_session, vault, COMICS)
    claims = (
        (await async_session.execute(select(VaultCollectible).where(VaultCollectible.vault_id == vault.id)))
        .scalars()
        .all()
    )
    for claim in claims:
        claim.finder_dweller_id = None
    await async_session.commit()

    assert await _multiplier(async_session, vault, EXPEDITION_LOOT_PCT) == pytest.approx(1.10)
    progress = {row.set: row for row in await collectible_service.set_progress(async_session, vault_id=vault.id)}
    assert (progress["comics"].held, progress["comics"].active) == (3, True)


async def test_the_comic_set_scales_settled_caps_and_leaves_the_run_haul_alone(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch: pytest.MonkeyPatch
) -> None:
    """3/3 pays 1.10x at the one place caps are credited — never 1.21x, never into the run."""
    monkeypatch.setattr(game_config.features, "collectibles", True)
    await _hold(async_session, vault, COMICS)
    await async_session.commit()
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    exploration.total_caps_found = 100
    async_session.add(exploration)
    await async_session.commit()
    before = vault.bottle_caps

    rewards = await rewards_service.apply_rewards(async_session, exploration)

    await async_session.refresh(vault)
    await async_session.refresh(exploration)
    assert rewards.caps == 110
    assert vault.bottle_caps == before + 110
    assert exploration.total_caps_found == 100
