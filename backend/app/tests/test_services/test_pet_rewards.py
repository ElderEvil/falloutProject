"""Pet bonus wiring at exploration settlement (pets plan §5.3).

The equipped pet's ``caps_pct`` scales the caps awarded by
``rewards_service.apply_rewards``; the pet's ``xp_pct`` scales XP in
``rewards_calculator.calculate_exploration_xp`` (unit-tested in
``test_rewards_calculator.py``). Both percentages are additive and capped by
``MAX_PCT_BONUS``.
"""

from unittest.mock import patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import RarityEnum
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.vault import Vault
from app.options.pet_modifiers import MAX_PCT_BONUS, PetEffect
from app.services.exploration.rewards_service import rewards_service
from app.services.exploration_service import exploration_service


def _pet_data(**overrides) -> dict:
    return {
        "name": "CX404",
        "rarity": RarityEnum.LEGENDARY,
        "value": 500,
        **overrides,
    }


async def _settled_exploration(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, caps: int
) -> Exploration:
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    exploration.total_caps_found = caps
    async_session.add(exploration)
    await async_session.commit()
    return exploration


@pytest.mark.asyncio
async def test_apply_rewards_applies_pet_caps_bonus(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A pet with caps_pct scales the awarded caps at settlement."""
    pet = await crud.pet.create(async_session, _pet_data())
    await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)

    exploration = await _settled_exploration(async_session, vault, dweller, caps=100)
    initial_caps = vault.bottle_caps

    rewards = await rewards_service.apply_rewards(async_session, exploration)

    await async_session.refresh(vault)
    assert rewards.caps == 125  # 100 * (1 + 0.25)
    assert vault.bottle_caps == initial_caps + 125


@pytest.mark.asyncio
async def test_apply_rewards_caps_pet_bonus_at_max_pct(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """caps_pct above MAX_PCT_BONUS is clamped at settlement."""
    exploration = await _settled_exploration(async_session, vault, dweller, caps=100)

    with patch(
        "app.services.exploration.rewards_service.pet_modifiers_for",
        return_value=PetEffect(caps_pct=0.8),
    ):
        rewards = await rewards_service.apply_rewards(async_session, exploration)

    assert rewards.caps == int(100 * (1 + MAX_PCT_BONUS))


@pytest.mark.asyncio
async def test_apply_rewards_without_pet_unchanged(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """No equipped pet means caps are awarded exactly as found."""
    exploration = await _settled_exploration(async_session, vault, dweller, caps=100)
    initial_caps = vault.bottle_caps

    rewards = await rewards_service.apply_rewards(async_session, exploration)

    await async_session.refresh(vault)
    assert rewards.caps == 100
    assert vault.bottle_caps == initial_caps + 100
