"""Shared arrangements for the exploration loot/equip suites (#765 workstreams 2-3)."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, patch

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import OutfitTypeEnum, RarityEnum, WeaponSubtypeEnum, WeaponTypeEnum
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.outfit import Outfit
from app.models.storage import Storage
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.schemas.exploration_event import LootEventSchema, LootSchema, OutfitSchema, WeaponSchema
from app.services.exploration.event_service import event_service


async def vault_storage_factory(async_session: AsyncSession, vault: Vault) -> Callable[[int], Awaitable[Storage]]:
    """Factory for the test vault's storage, emptied and sized via max_space."""
    result = await async_session.execute(select(Storage).where(Storage.vault_id == vault.id))
    storage = result.scalar_one_or_none() or await vault_crud.create_storage(
        db_session=async_session, vault_id=vault.id
    )

    async def _make(max_space: int = 10) -> Storage:
        storage.max_space = max_space
        storage.used_space = 0
        async_session.add(storage)
        await async_session.flush()
        return storage

    return _make


async def equip_weapon(
    async_session: AsyncSession,
    dweller: Dweller,
    *,
    name: str,
    rarity: RarityEnum,
    damage_min: int,
    damage_max: int,
    value: int = 10,
) -> Weapon:
    weapon = Weapon(
        name=name,
        rarity=rarity,
        value=value,
        weapon_type=WeaponTypeEnum.GUN,
        weapon_subtype=WeaponSubtypeEnum.PISTOL,
        stat="agility",
        damage_min=damage_min,
        damage_max=damage_max,
        dweller_id=dweller.id,
    )
    async_session.add(weapon)
    await async_session.flush()
    return weapon


async def equip_outfit(
    async_session: AsyncSession,
    dweller: Dweller,
    *,
    name: str,
    rarity: RarityEnum,
    value: int,
    outfit_type: OutfitTypeEnum,
) -> Outfit:
    outfit = Outfit(name=name, rarity=rarity, value=value, outfit_type=outfit_type, dweller_id=dweller.id)
    async_session.add(outfit)
    await async_session.flush()
    return outfit


def weapon_loot_event(name: str, rarity: str, damage_min: int, damage_max: int, value: int) -> LootEventSchema:
    item = WeaponSchema(
        name=name,
        rarity=rarity,
        value=value,
        weapon_type="MELEE",
        weapon_subtype="BLUNT",
        stat="strength",
        damage_min=damage_min,
        damage_max=damage_max,
    )
    return LootEventSchema(description=f"Found a {name}", loot=LootSchema(item=item, item_type="weapon", caps=5))


def outfit_loot_event(name: str, rarity: str, value: int, outfit_type: str) -> LootEventSchema:
    item = OutfitSchema(name=name, rarity=rarity, value=value, outfit_type=outfit_type)
    return LootEventSchema(description=f"Found a {name}", loot=LootSchema(item=item, item_type="outfit", caps=5))


async def process_loot_event(async_session: AsyncSession, exploration, loot_event: LootEventSchema) -> AsyncMock:
    """Run one loot event through the real event service and return the notify mock."""
    with (
        patch("app.services.exploration.event_service.event_generator.generate_event", return_value=loot_event),
        patch("app.services.exploration.event_service.sse_manager.publish", new_callable=AsyncMock),
        patch(
            "app.services.exploration.event_service.notification_service.notify_exploration_update",
            new_callable=AsyncMock,
        ) as notify,
    ):
        await event_service.process_event(async_session, exploration)
    return notify


async def equipped_weapon_names(async_session: AsyncSession, dweller: Dweller) -> list[str]:
    rows = (await async_session.execute(select(Weapon).where(Weapon.dweller_id == dweller.id))).scalars().all()
    return [weapon.name for weapon in rows]


async def held_weapons(async_session: AsyncSession, exploration) -> list[Weapon]:
    rows = await async_session.execute(select(Weapon).where(Weapon.exploration_id == exploration.id))
    return list(rows.scalars().all())
