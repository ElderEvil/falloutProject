"""Reward service for granting rewards when quests and objectives are completed."""

import logging
import random
from typing import Any

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.dweller import Dweller
from app.models.outfit import Outfit
from app.models.quest import Quest
from app.models.quest_reward import QuestReward, RewardType
from app.models.storage import Storage
from app.models.vault_objective import VaultObjectiveProgressLink
from app.models.weapon import Weapon
from app.schemas.vault import VaultUpdate
from app.services.event_bus import GameEvent, event_bus

logger = logging.getLogger(__name__)


class RewardService:
    """Service for processing and granting quest/objective rewards."""

    async def grant_caps(self, db_session: AsyncSession, vault_id: UUID4, amount: int) -> dict[str, Any]:
        from app.crud.vault import vault as vault_crud

        vault_obj = await vault_crud.get(db_session, id=vault_id)
        await vault_crud.deposit_caps(db_session=db_session, vault_obj=vault_obj, amount=amount)

        logger.info(f"Granted {amount} caps to vault {vault_id}")
        return {"reward_type": RewardType.CAPS, "amount": amount}

    async def grant_item(self, db_session: AsyncSession, vault_id: UUID4, item_data: dict[str, Any]) -> dict[str, Any]:
        from app.crud.storage import get_available_space

        result = await db_session.execute(select(Storage).where(Storage.vault_id == vault_id))
        storage_obj = result.scalar_one_or_none()
        if not storage_obj:
            msg = f"No storage found for vault {vault_id}"
            logger.warning(msg)
            raise ValueError(msg)

        available = await get_available_space(db_session, storage_obj.id)
        if available <= 0:
            msg = f"Storage full for vault {vault_id}"
            logger.warning(msg)
            raise ValueError(msg)

        item_type = item_data.get("item_type", "weapon")
        item_name = item_data.get("name", "Unknown Item")
        item_rarity = item_data.get("rarity", "common")

        if item_type == "weapon":
            weapon = Weapon(
                name=item_name,
                rarity=item_rarity,
                weapon_type=item_data.get("weapon_type", "melee"),
                weapon_subtype=item_data.get("weapon_subtype", "blunt"),
                stat=item_data.get("stat", "strength"),
                damage_min=item_data.get("damage_min", 1),
                damage_max=item_data.get("damage_max", 3),
                value=item_data.get("value"),
                storage_id=storage_obj.id,
            )
            db_session.add(weapon)
            await db_session.commit()
            await db_session.refresh(weapon)
            await event_bus.emit(GameEvent.ITEM_COLLECTED, vault_id, {"item_type": "weapon", "amount": 1})
            logger.info(f"Granted weapon '{item_name}' ({item_rarity}) to vault {vault_id}")
            return {"reward_type": RewardType.ITEM, "item_type": "weapon", "name": item_name, "item_id": str(weapon.id)}

        if item_type == "outfit":
            outfit = Outfit(
                name=item_name,
                rarity=item_rarity,
                outfit_type=item_data.get("outfit_type", "suit"),
                gender=item_data.get("gender"),
                value=item_data.get("value"),
                storage_id=storage_obj.id,
            )
            db_session.add(outfit)
            await db_session.commit()
            await db_session.refresh(outfit)
            await event_bus.emit(GameEvent.ITEM_COLLECTED, vault_id, {"item_type": "outfit", "amount": 1})
            logger.info(f"Granted outfit '{item_name}' ({item_rarity}) to vault {vault_id}")
            return {
                "reward_type": RewardType.ITEM,
                "item_type": "outfit",
                "name": item_name,
                "item_id": str(outfit.id),
            }

        msg = f"Unknown item_type: {item_type}"
        raise ValueError(msg)

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

        try:
            rarity_enum = RarityEnum(rarity)
        except ValueError:
            rarity_enum = RarityEnum.COMMON

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
            vault_id=vault_id,
        )
        db_session.add(new_dweller)
        await db_session.commit()
        await db_session.refresh(new_dweller)

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

        match resource_type.lower():
            case "food":
                new_value = min(vault_obj.food + amount, vault_obj.food_max)
                await vault_crud.update(db_session, id=vault_id, obj_in=VaultUpdate(food=new_value))
            case "water":
                new_value = min(vault_obj.water + amount, vault_obj.water_max)
                await vault_crud.update(db_session, id=vault_id, obj_in=VaultUpdate(water=new_value))
            case "power":
                new_value = min(vault_obj.power + amount, vault_obj.power_max)
                await vault_crud.update(db_session, id=vault_id, obj_in=VaultUpdate(power=new_value))
            case _:
                msg = f"Invalid resource_type: {resource_type}. Must be 'food', 'water', or 'power'"
                raise ValueError(msg)

        logger.info(f"Granted {amount} {resource_type} to vault {vault_id}")
        return {"reward_type": RewardType.RESOURCE, "resource_type": resource_type, "amount": amount}

    async def grant_experience(self, db_session: AsyncSession, dweller_ids: list[UUID4], amount: int) -> dict[str, Any]:
        from app.crud.dweller import dweller as dweller_crud

        leveled_up: list[str] = []
        granted_to: list[str] = []

        for dweller_id in dweller_ids:
            try:
                dweller_obj = await dweller_crud.get(db_session, id=dweller_id)
                old_level = dweller_obj.level
                await dweller_crud.add_experience(db_session, dweller_obj, amount)
                granted_to.append(str(dweller_id))

                await db_session.refresh(dweller_obj)
                if dweller_obj.level > old_level:
                    leveled_up.append(str(dweller_id))
            except Exception:
                logger.exception(f"Failed to grant {amount} XP to dweller {dweller_id}")

        logger.info(f"Granted {amount} XP to {len(granted_to)} dweller(s), {len(leveled_up)} leveled up")
        return {
            "reward_type": RewardType.EXPERIENCE,
            "amount": amount,
            "dweller_ids": granted_to,
            "leveled_up": leveled_up,
        }

    async def grant_stimpak(self, db_session: AsyncSession, vault_id: UUID4, amount: int) -> dict[str, Any]:
        """Grant stimpaks to random dweller in vault."""
        from app.crud.dweller import dweller as dweller_crud

        # Get dwellers in vault
        dwellers = await dweller_crud.get_multi_by_vault(db_session, vault_id=vault_id, skip=0, limit=100)
        dwellers = [d for d in dwellers if not d.is_deleted]

        if not dwellers:
            logger.warning(f"No dwellers found in vault {vault_id} to grant stimpaks")
            return {"reward_type": RewardType.STIMPAK, "amount": 0, "message": "No dwellers found"}

        # Grant to random dweller
        dweller = dwellers[0]
        dweller.stimpack = (dweller.stimpack or 0) + amount
        db_session.add(dweller)
        await db_session.commit()
        await event_bus.emit(GameEvent.ITEM_COLLECTED, vault_id, {"item_type": "stimpak", "amount": amount})

        logger.info(f"Granted {amount} stimpaks to dweller {dweller.first_name} in vault {vault_id}")
        return {"reward_type": RewardType.STIMPAK, "amount": amount, "dweller_id": str(dweller.id)}

    async def grant_radaway(self, db_session: AsyncSession, vault_id: UUID4, amount: int) -> dict[str, Any]:
        """Grant radaways to random dweller in vault."""
        from app.crud.dweller import dweller as dweller_crud

        # Get dwellers in vault
        dwellers = await dweller_crud.get_multi_by_vault(db_session, vault_id=vault_id, skip=0, limit=100)
        dwellers = [d for d in dwellers if not d.is_deleted]

        if not dwellers:
            logger.warning(f"No dwellers found in vault {vault_id} to grant radaways")
            return {"reward_type": RewardType.RADAWAY, "amount": 0, "message": "No dwellers found"}

        # Grant to random dweller
        dweller = dwellers[0]
        dweller.radaway = (dweller.radaway or 0) + amount
        db_session.add(dweller)
        await db_session.commit()

        logger.info(f"Granted {amount} radaways to dweller {dweller.first_name} in vault {vault_id}")
        return {"reward_type": RewardType.RADAWAY, "amount": amount, "dweller_id": str(dweller.id)}

    async def grant_lunchbox(self, db_session: AsyncSession, vault_id: UUID4) -> dict[str, Any]:
        """Grant a lunchbox (gives random rare dwellers/items).

        Lunchbox rewards give:
        - 3 random items (weapons or outfits)
        - 1 random dweller
        """
        import random

        from sqlmodel import select

        from app.models.outfit import Outfit
        from app.models.storage import Storage
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
                weights=[0.6, 0.2, 0.1],
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
                )
            else:
                gender = random.choice([GenderEnum.MALE, GenderEnum.FEMALE])
                item = Outfit(
                    name=name,
                    rarity=rarity.value,
                    outfit_type=wtype,
                    gender=gender,
                    value=random.randint(30, 100),
                )

            # Get storage
            result = await db_session.execute(select(Storage).where(Storage.vault_id == vault_id))
            storage = result.scalar_one_or_none()
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

        await db_session.commit()

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

            try:
                result = await self._process_single_reward(db_session, vault_id, reward.reward_type, reward.reward_data)
                granted_rewards.append(result)
            except Exception:
                logger.exception(
                    f"Failed to process {reward.reward_type} reward for quest '{quest.title}' in vault {vault_id}"
                )

        logger.info(f"Processed {len(granted_rewards)}/{len(rewards)} rewards for quest '{quest.title}'")
        return granted_rewards

    async def process_objective_reward(
        self, db_session: AsyncSession, vault_id: UUID4, objective: VaultObjectiveProgressLink
    ) -> dict[str, Any] | None:
        from app.crud.objective import objective_crud

        objective_obj = await objective_crud.get(db_session, id=objective.objective_id)
        reward_str = objective_obj.reward

        try:
            reward_type, reward_data = self._parse_objective_reward(reward_str)
            result = await self._process_single_reward(db_session, vault_id, reward_type, reward_data)
            logger.info(f"Processed objective reward '{reward_str}' for vault {vault_id}")
            return result
        except Exception:
            logger.exception(f"Failed to process objective reward '{reward_str}' for vault {vault_id}")
            return None

    async def _process_single_reward(  # noqa: PLR0911
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        reward_type: RewardType | str,
        reward_data: dict[str, Any],
    ) -> dict[str, Any]:
        reward_type_str = reward_type.value if isinstance(reward_type, RewardType) else reward_type

        match reward_type_str:
            case RewardType.CAPS:
                return await self.grant_caps(db_session, vault_id, reward_data.get("amount", 0))
            case RewardType.ITEM:
                return await self.grant_item(db_session, vault_id, reward_data)
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
                return await self.grant_stimpak(db_session, vault_id, reward_data.get("amount", 1))
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
        if len(parts) == 2:
            try:
                amount = int(parts[0])
                reward_name = parts[1].lower().strip()

                if reward_name == "caps":
                    return RewardType.CAPS, {"amount": amount}
                if reward_name in ("food", "water", "power"):
                    return RewardType.RESOURCE, {"resource_type": reward_name, "amount": amount}
                if reward_name in ("xp", "experience"):
                    return RewardType.EXPERIENCE, {"amount": amount, "dweller_ids": []}
            except ValueError:
                pass

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
