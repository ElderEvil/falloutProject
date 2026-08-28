"""Reward service for granting rewards when quests and objectives are completed."""

import logging
import random
from typing import Any

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.storage import storage as storage_crud
from app.models.dweller import Dweller
from app.models.outfit import Outfit
from app.models.quest import Quest
from app.models.quest_reward import QuestReward, RewardType
from app.models.storage import Storage
from app.models.vault_objective import VaultObjectiveProgressLink
from app.models.weapon import Weapon
from app.services.event_bus import GameEvent, event_bus
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException
from app.utils.outfit_assets import get_outfit_image_url
from app.utils.reward_delivery import persist_reward_change, reward_delivery_is_deferred
from app.utils.weapon_assets import get_weapon_image_url

logger = logging.getLogger(__name__)


class RewardService:
    """Service for processing and granting quest/objective rewards."""

    async def grant_caps(
        self, db_session: AsyncSession, vault_id: UUID4, amount: int, *, emit_event: bool = True
    ) -> dict[str, Any]:
        from app.crud.vault import vault as vault_crud

        vault_obj = await vault_crud.get(db_session, id=vault_id)
        if reward_delivery_is_deferred(db_session):
            vault_obj.bottle_caps += amount
            await persist_reward_change(db_session, vault_obj)
        else:
            await vault_crud.deposit_caps(
                db_session=db_session, vault_obj=vault_obj, amount=amount, emit_event=emit_event
            )

        logger.info(f"Granted {amount} caps to vault {vault_id}")
        return {"reward_type": RewardType.CAPS, "amount": amount}

    async def grant_item(
        self, db_session: AsyncSession, vault_id: UUID4, item_data: dict[str, Any], *, emit_event: bool = True
    ) -> dict[str, Any]:
        from app.crud.storage import get_available_space

        storage_obj = await storage_crud.get_by_vault(db_session, vault_id)
        if not storage_obj:
            msg = f"No storage found for vault {vault_id}"
            logger.warning(msg)
            raise ResourceNotFoundException(Storage, vault_id, identifier_type="vault_id")

        available = await get_available_space(db_session, storage_obj.id)
        if available <= 0:
            msg = f"Storage full for vault {vault_id}"
            logger.warning(msg)
            raise ResourceConflictException(msg)

        item_type = item_data.get("item_type", "weapon")
        item_name = item_data.get("name", "Unknown Item")
        item_rarity = item_data.get("rarity", "common")

        match item_type:
            case "weapon":
                item = Weapon(
                    name=item_name,
                    rarity=item_rarity,
                    weapon_type=item_data.get("weapon_type", "melee"),
                    weapon_subtype=item_data.get("weapon_subtype", "blunt"),
                    stat=item_data.get("stat", "strength"),
                    damage_min=item_data.get("damage_min", 1),
                    damage_max=item_data.get("damage_max", 3),
                    value=item_data.get("value"),
                    image_url=get_weapon_image_url(item_name),
                    storage_id=storage_obj.id,
                )
            case "outfit":
                item = Outfit(
                    name=item_name,
                    rarity=item_rarity,
                    outfit_type=item_data.get("outfit_type", "suit"),
                    gender=item_data.get("gender"),
                    value=item_data.get("value"),
                    image_url=get_outfit_image_url(item_name),
                    storage_id=storage_obj.id,
                )
            case _:
                msg = f"Unknown item_type: {item_type}"
                raise ValueError(msg)

        await persist_reward_change(db_session, item, refresh=True)
        if emit_event and not reward_delivery_is_deferred(db_session):
            await event_bus.emit(GameEvent.ITEM_COLLECTED, vault_id, {"item_type": item_type, "amount": 1})
        logger.info(f"Granted {item_type} '{item_name}' ({item_rarity}) to vault {vault_id}")
        return {"reward_type": RewardType.ITEM, "item_type": item_type, "name": item_name, "item_id": str(item.id)}

    async def grant_dweller(
        self, db_session: AsyncSession, vault_id: UUID4, dweller_template: dict[str, Any]
    ) -> dict[str, Any]:
        from app.schemas.common import RarityEnum
        from app.schemas.dweller import STATS_RANGE_BY_RARITY

        first_name = dweller_template.get("first_name", dweller_template.get("name", "Unknown"))
        last_name = dweller_template.get("last_name")
        rarity = dweller_template.get("rarity", "common")
        level = dweller_template.get("level", 1)
        gender = dweller_template.get("gender", "male")

        rarity_enum = RarityEnum(rarity)

        stat_range = STATS_RANGE_BY_RARITY.get(rarity_enum, (1, 3))
        default_stat = random.randint(stat_range[0], stat_range[1])

        new_dweller = Dweller(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            rarity=rarity_enum,
            level=level,
            experience=dweller_template.get("experience", 0),
            max_health=dweller_template.get("max_health", 50),
            health=dweller_template.get("health", 50),
            happiness=dweller_template.get("happiness", 50),
            strength=dweller_template.get("strength", default_stat),
            perception=dweller_template.get("perception", default_stat),
            endurance=dweller_template.get("endurance", default_stat),
            charisma=dweller_template.get("charisma", default_stat),
            intelligence=dweller_template.get("intelligence", default_stat),
            agility=dweller_template.get("agility", default_stat),
            luck=dweller_template.get("luck", default_stat),
            bio=dweller_template.get("bio"),
            vault_id=vault_id,
        )
        await persist_reward_change(db_session, new_dweller, refresh=True)

        logger.info(f"Granted dweller '{first_name}' ({rarity}) to vault {vault_id}")
        return {
            "reward_type": RewardType.DWELLER,
            "dweller_id": str(new_dweller.id),
            "name": f"{first_name} {last_name or ''}".strip(),
        }

    async def grant_resource(
        self, db_session: AsyncSession, vault_id: UUID4, resource_type: str, amount: int
    ) -> dict[str, Any]:
        from app.crud.vault import vault as vault_crud

        vault_obj = await vault_crud.get(db_session, id=vault_id)
        deferred = reward_delivery_is_deferred(db_session)

        match resource_type.lower():
            case "food":
                new_value = min(vault_obj.food + amount, vault_obj.food_max)
                field = "food"
            case "water":
                new_value = min(vault_obj.water + amount, vault_obj.water_max)
                field = "water"
            case "power":
                new_value = min(vault_obj.power + amount, vault_obj.power_max)
                field = "power"
            case _:
                msg = f"Invalid resource_type: {resource_type}. Must be 'food', 'water', or 'power'"
                raise ValueError(msg)

        if deferred:
            setattr(vault_obj, field, new_value)
            await persist_reward_change(db_session, vault_obj)
        else:
            await vault_crud.update(db_session, id=vault_id, obj_in={field: new_value})

        logger.info(f"Granted {amount} {resource_type} to vault {vault_id}")
        return {"reward_type": RewardType.RESOURCE, "resource_type": resource_type, "amount": amount}

    async def grant_experience(self, db_session: AsyncSession, dweller_ids: list[UUID4], amount: int) -> dict[str, Any]:
        from app.crud.dweller import dweller as dweller_crud

        leveled_up: list[str] = []
        granted_to: list[str] = []

        for raw_id in dweller_ids:
            dweller_id = UUID4(raw_id) if isinstance(raw_id, str) else raw_id
            dweller_obj = await dweller_crud.get(db_session, id=dweller_id)
            old_level = dweller_obj.level
            await dweller_crud.add_experience(db_session, dweller_obj, amount)
            granted_to.append(str(dweller_id))

            await db_session.refresh(dweller_obj)
            if dweller_obj.level > old_level:
                leveled_up.append(str(dweller_id))

        logger.info(f"Granted {amount} XP to {len(granted_to)} dweller(s), {len(leveled_up)} leveled up")
        return {
            "reward_type": RewardType.EXPERIENCE,
            "amount": amount,
            "dweller_ids": granted_to,
            "leveled_up": leveled_up,
        }

    async def grant_stimpak(
        self, db_session: AsyncSession, vault_id: UUID4, amount: int, *, emit_event: bool = True
    ) -> dict[str, Any]:
        """Grant stimpaks to random dweller in vault."""
        return await self._grant_medication(
            db_session, vault_id, amount, RewardType.STIMPAK, "stimpack", emit_event=emit_event
        )

    async def grant_radaway(self, db_session: AsyncSession, vault_id: UUID4, amount: int) -> dict[str, Any]:
        """Grant radaways to random dweller in vault."""
        return await self._grant_medication(db_session, vault_id, amount, RewardType.RADAWAY, "radaway")

    async def _grant_medication(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        amount: int,
        reward_type: RewardType,
        stock_field: str,
        *,
        emit_event: bool = False,
    ) -> dict[str, Any]:
        from app.crud.dweller import dweller as dweller_crud

        dwellers = await dweller_crud.get_multi_by_vault(db_session, vault_id=vault_id, skip=0, limit=100)
        if not dwellers:
            logger.warning(f"No dwellers found in vault {vault_id} to grant {reward_type}s")
            return {"reward_type": reward_type, "amount": 0, "message": "No dwellers found"}

        dweller = random.choice(dwellers)
        setattr(dweller, stock_field, (getattr(dweller, stock_field) or 0) + amount)
        await persist_reward_change(db_session, dweller)
        if emit_event and not reward_delivery_is_deferred(db_session):
            await event_bus.emit(GameEvent.ITEM_COLLECTED, vault_id, {"item_type": reward_type, "amount": amount})

        logger.info(f"Granted {amount} {reward_type}s to dweller {dweller.first_name} in vault {vault_id}")
        return {"reward_type": reward_type, "amount": amount, "dweller_id": str(dweller.id)}

    async def grant_lunchbox(self, db_session: AsyncSession, vault_id: UUID4) -> dict[str, Any]:
        """Grant a lunchbox (gives random rare dwellers/items).

        Lunchbox rewards give:
        - 3 random items (weapons or outfits)
        - 1 random dweller
        """
        from app.models.outfit import Outfit
        from app.models.weapon import Weapon
        from app.schemas.common import GenderEnum, OutfitTypeEnum, RarityEnum, WeaponSubtypeEnum, WeaponTypeEnum

        # Generate 3 random items
        item_configs = [
            ("Laser Pistol", WeaponTypeEnum.ENERGY, WeaponSubtypeEnum.PISTOL, "luck"),
            ("Plasma Pistol", WeaponTypeEnum.ENERGY, WeaponSubtypeEnum.PISTOL, "luck"),
            ("Assault Rifle", WeaponTypeEnum.GUN, WeaponSubtypeEnum.RIFLE, "agility"),
            ("Vault Suit", OutfitTypeEnum.COMMON, None, "endurance"),
            ("Combat Armor", OutfitTypeEnum.POWER_ARMOR, None, "endurance"),
        ]
        granted_items = []
        for _ in range(3):
            name, wtype, subtype, stat = random.choice(item_configs)

            rarity = random.choices(
                [RarityEnum.COMMON, RarityEnum.RARE, RarityEnum.LEGENDARY],
                weights=[0.7, 0.2, 0.1],
            )[0]

            if wtype in (WeaponTypeEnum.MELEE, WeaponTypeEnum.GUN, WeaponTypeEnum.ENERGY, WeaponTypeEnum.HEAVY):
                item = Weapon(
                    name=name,
                    rarity=rarity.value,
                    weapon_type=wtype,
                    weapon_subtype=subtype,
                    stat=stat,
                    damage_min=random.randint(2, 5),
                    damage_max=random.randint(5, 10),
                    value=random.randint(50, 200),
                    image_url=get_weapon_image_url(name),
                )
            else:
                gender = random.choice([GenderEnum.MALE, GenderEnum.FEMALE])
                item = Outfit(
                    name=name,
                    rarity=rarity.value,
                    outfit_type=wtype,
                    gender=gender,
                    value=random.randint(30, 100),
                    image_url=get_outfit_image_url(name),
                )

            # Get storage
            storage = await storage_crud.get_by_vault(db_session, vault_id)
            if storage:
                item.storage_id = storage.id
                db_session.add(item)
                granted_items.append(
                    {"name": name, "type": "weapon" if isinstance(item, Weapon) else "outfit", "rarity": rarity.value}
                )

        # Generate random dweller
        dweller_data = {
            "first_name": random.choice(
                [
                    "Albert",
                    "Brian",
                    "Charles",
                    "David",
                    "Edward",
                    "Frank",
                    "Amy",
                    "Betty",
                    "Carol",
                    "Donna",
                    "Emily",
                    "Fiona",
                ]
            ),
            "last_name": random.choice(["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller"]),
            "rarity": random.choice([RarityEnum.COMMON, RarityEnum.RARE, RarityEnum.LEGENDARY]),
            "level": random.randint(1, 5),
            "gender": random.choice([GenderEnum.MALE, GenderEnum.FEMALE]),
        }
        granted_dweller = await self.grant_dweller(db_session, vault_id, dweller_data)

        await persist_reward_change(db_session)

        logger.info(f"Granted lunchbox to vault {vault_id}: {len(granted_items)} items, 1 dweller")
        return {
            "reward_type": RewardType.LUNCHBOX,
            "items": granted_items,
            "dweller": granted_dweller,
        }

    async def process_quest_rewards(
        self, db_session: AsyncSession, vault_id: UUID4, quest: Quest
    ) -> list[dict[str, Any]]:
        granted_rewards: list[dict[str, Any]] = []

        rewards: list[QuestReward] = quest.quest_rewards
        if not rewards:
            logger.info(f"Quest '{quest.title}' has no rewards to process")
            return granted_rewards

        for reward in rewards:
            if reward.reward_chance < 1.0 and random.random() > reward.reward_chance:
                logger.debug(f"Reward roll failed for quest '{quest.title}' (chance={reward.reward_chance:.3f})")
                continue

            result = await self._process_single_reward(db_session, vault_id, reward.reward_type, reward.reward_data)
            granted_rewards.append(result)

        logger.info(f"Processed {len(granted_rewards)}/{len(rewards)} rewards for quest '{quest.title}'")
        return granted_rewards

    async def process_objective_reward(
        self, db_session: AsyncSession, vault_id: UUID4, objective: VaultObjectiveProgressLink
    ) -> dict[str, Any]:
        from app.crud.objective import objective_crud

        objective_obj = await objective_crud.get(db_session, id=objective.objective_id)
        reward_str = objective_obj.reward

        reward_type, reward_data = self._parse_objective_reward(reward_str)
        result = await self._process_single_reward(db_session, vault_id, reward_type, reward_data, emit_event=False)
        logger.info(f"Processed objective reward '{reward_str}' for vault {vault_id}")
        return result

    async def _process_single_reward(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        reward_type: RewardType | str,
        reward_data: dict[str, Any],
        *,
        emit_event: bool = True,
    ) -> dict[str, Any]:
        reward_type_str = reward_type.value if isinstance(reward_type, RewardType) else reward_type

        match reward_type_str:
            case RewardType.CAPS:
                return await self.grant_caps(db_session, vault_id, reward_data.get("amount", 0), emit_event=emit_event)
            case RewardType.ITEM:
                return await self.grant_item(db_session, vault_id, reward_data, emit_event=emit_event)
            case RewardType.DWELLER:
                return await self.grant_dweller(db_session, vault_id, reward_data)
            case RewardType.RESOURCE:
                return await self.grant_resource(
                    db_session, vault_id, reward_data.get("resource_type", "food"), reward_data.get("amount", 0)
                )
            case RewardType.EXPERIENCE:
                return await self.grant_experience(
                    db_session, reward_data.get("dweller_ids", []), reward_data.get("amount", 0)
                )
            case RewardType.STIMPAK:
                return await self.grant_stimpak(
                    db_session, vault_id, reward_data.get("amount", 1), emit_event=emit_event
                )
            case RewardType.RADAWAY:
                return await self.grant_radaway(db_session, vault_id, reward_data.get("amount", 1))
            case RewardType.LUNCHBOX:
                return await self.grant_lunchbox(db_session, vault_id)
            case _:
                msg = f"Unknown reward type: {reward_type_str}"
                raise ValueError(msg)

    @staticmethod
    def _parse_objective_reward(reward_str: str) -> tuple[RewardType, dict[str, Any]]:
        """Parse objective reward string into (RewardType, data).

        Formats: "100 caps", "50 food", "200 xp", "weapon:Laser Pistol", "outfit:Vault Suit", "dweller:Wanderer"
        """
        reward_str = reward_str.strip()

        parts = reward_str.split(maxsplit=1)
        if len(parts) == 2 and parts[0].isdigit():
            amount = int(parts[0])
            reward_name = parts[1].lower().strip()

            if reward_name == "caps":
                return RewardType.CAPS, {"amount": amount}
            if reward_name in ("food", "water", "power"):
                return RewardType.RESOURCE, {"resource_type": reward_name, "amount": amount}
            if reward_name in ("xp", "experience"):
                return RewardType.EXPERIENCE, {"amount": amount, "dweller_ids": []}

        if ":" in reward_str:
            prefix, value = reward_str.split(":", 1)
            prefix = prefix.lower().strip()
            value = value.strip()

            if prefix == "weapon":
                return RewardType.ITEM, {"item_type": "weapon", "name": value, "rarity": "common"}
            if prefix == "outfit":
                return RewardType.ITEM, {"item_type": "outfit", "name": value, "rarity": "common"}
            if prefix == "dweller":
                return RewardType.DWELLER, {"first_name": value, "rarity": "common"}

        msg = f"Cannot parse objective reward string: '{reward_str}'"
        raise ValueError(msg)


reward_service = RewardService()
