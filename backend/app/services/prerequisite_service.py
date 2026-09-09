"""Prerequisite service for validating quest requirements before a vault can start a quest."""

import logging
from typing import Any

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement, RequirementType
from app.utils.objective_constants import normalize_room_type

logger = logging.getLogger(__name__)


class PrerequisiteService:
    """Service for checking whether a vault meets all requirements to start a quest."""

    async def validate_level_requirement(
        self, db_session: AsyncSession, vault_id: UUID4, requirement_data: dict[str, Any]
    ) -> bool:
        required_level = requirement_data.get("level", 1)
        required_count = requirement_data.get("count", 1)

        matching_count = await crud.dweller.count_alive_in_vault(db_session, vault_id, min_level=required_level)
        return matching_count >= required_count

    async def validate_item_requirement(
        self, db_session: AsyncSession, vault_id: UUID4, requirement_data: dict[str, Any]
    ) -> bool:
        item_name = requirement_data.get("item_name", "")
        required_count = requirement_data.get("count", 1)

        storage = await crud.storage.get_by_vault(db_session, vault_id)
        if not storage:
            return False

        weapon_count = await crud.weapon.count_in_storage_by_name(db_session, storage.id, item_name)
        outfit_count = await crud.outfit.count_in_storage_by_name(db_session, storage.id, item_name)

        return weapon_count + outfit_count >= required_count

    async def validate_room_requirement(
        self, db_session: AsyncSession, vault_id: UUID4, requirement_data: dict[str, Any]
    ) -> bool:
        room_type = normalize_room_type(requirement_data.get("room_type"))
        required_count = requirement_data.get("count", 1)
        if room_type is None:
            return False

        room_names = await crud.dweller.count_room_names_by_type(db_session, vault_id)
        return sum(normalize_room_type(name) == room_type for name in room_names) >= required_count

    async def validate_dweller_count_requirement(
        self, db_session: AsyncSession, vault_id: UUID4, requirement_data: dict[str, Any]
    ) -> bool:
        required_count = requirement_data.get("count", 0)

        current_count = await crud.dweller.count_alive_in_vault(db_session, vault_id)
        return current_count >= required_count

    async def validate_quest_completed_requirement(
        self, db_session: AsyncSession, vault_id: UUID4, requirement_data: dict[str, Any]
    ) -> bool:
        quest_id = requirement_data.get("quest_id")
        if not quest_id:
            logger.warning("quest_completed requirement missing quest_id")
            return False

        link = await crud.quest_crud.get_link(db_session, quest_id=quest_id, vault_id=vault_id)
        return link is not None and link.is_completed

    async def can_start_quest(self, db_session: AsyncSession, vault_id: UUID4, quest: Quest) -> tuple[bool, list[str]]:
        missing = await self.get_missing_requirements(db_session, vault_id, quest)
        return len(missing) == 0, missing

    async def get_missing_requirements(self, db_session: AsyncSession, vault_id: UUID4, quest: Quest) -> list[str]:
        missing: list[str] = []
        requirements: list[QuestRequirement] = quest.quest_requirements

        if not requirements:
            return missing

        for req in requirements:
            is_met = await self._check_requirement(db_session, vault_id, req)

            if not is_met:
                if not req.is_mandatory:
                    logger.debug(
                        f"Optional requirement not met for quest '{quest.title}': "
                        f"{req.requirement_type} - {req.requirement_data}"
                    )
                    continue

                description = self._describe_requirement(req)
                missing.append(description)

        if missing:
            logger.info(f"Vault {vault_id} missing {len(missing)} requirement(s) for quest '{quest.title}': {missing}")

        return missing

    async def _check_requirement(
        self, db_session: AsyncSession, vault_id: UUID4, requirement: QuestRequirement
    ) -> bool:
        """Dispatch to the correct validation method based on requirement type."""
        validators = {
            RequirementType.LEVEL: self.validate_level_requirement,
            RequirementType.ITEM: self.validate_item_requirement,
            RequirementType.ROOM: self.validate_room_requirement,
            RequirementType.DWELLER_COUNT: self.validate_dweller_count_requirement,
            RequirementType.QUEST_COMPLETED: self.validate_quest_completed_requirement,
        }

        validator = validators.get(requirement.requirement_type)
        if not validator:
            logger.warning(f"Unknown requirement type: {requirement.requirement_type}")
            return False

        try:
            return await validator(db_session, vault_id, requirement.requirement_data)
        except Exception:
            logger.exception(f"Error validating {requirement.requirement_type} requirement for vault {vault_id}")
            return False

    @staticmethod
    def _describe_level(data: dict[str, Any]) -> str:
        level = data.get("level", "?")
        count = data.get("count", 1)
        if count > 1:
            return f"Need {count} dweller(s) at level {level} or higher"
        return f"Need a dweller at level {level} or higher"

    @staticmethod
    def _describe_item(data: dict[str, Any]) -> str:
        item_name = data.get("item_name", "Unknown item")
        count = data.get("count", 1)
        if count > 1:
            return f"Need {count}x {item_name} in storage"
        return f"Need {item_name} in storage"

    @staticmethod
    def _describe_room(data: dict[str, Any]) -> str:
        room_type = data.get("room_type", "Unknown room")
        room_display = room_type.replace("_", " ").title()
        count = data.get("count", 1)
        if count > 1:
            return f"Need {count} {room_display} room(s) built"
        return f"Need {room_display} built"

    @staticmethod
    def _describe_dweller_count(data: dict[str, Any]) -> str:
        count = data.get("count", 0)
        return f"Need at least {count} dwellers in vault"

    @staticmethod
    def _describe_quest_completed(data: dict[str, Any]) -> str:
        quest_id = data.get("quest_id", "Unknown")
        return f"Need to complete prerequisite quest (ID: {quest_id})"

    def _describe_requirement(self, requirement: QuestRequirement) -> str:
        describers = {
            RequirementType.LEVEL: self._describe_level,
            RequirementType.ITEM: self._describe_item,
            RequirementType.ROOM: self._describe_room,
            RequirementType.DWELLER_COUNT: self._describe_dweller_count,
            RequirementType.QUEST_COMPLETED: self._describe_quest_completed,
        }

        describer = describers.get(requirement.requirement_type)
        if not describer:
            return f"Unknown requirement: {requirement.requirement_type}"
        return describer(requirement.requirement_data)


prerequisite_service = PrerequisiteService()
