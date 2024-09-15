from collections.abc import Sequence

from pydantic import UUID4
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Dweller, Room, Vault
from app.schemas.common import SPECIALEnum
from app.schemas.vault import VaultUpdate

POWER_CONSUMPTION_RATE = 0.5 / 60
FOOD_CONSUMPTION_PER_DWELLER = 0.36 / 60
WATER_CONSUMPTION_PER_DWELLER = 0.36 / 60


class ResourceCalculator:
    @staticmethod
    async def _calculate_net_resource_change(
        vault: Vault,
        rooms: Sequence[Room],
        dweller_count: int,
        rooms_with_dwellers: list[tuple[Room, list[Dweller]]],
        seconds_passed: int,
    ) -> VaultUpdate:
        """
        Calculate net resource change considering both consumption and production.
        """
        # Initialize net change
        net_change = {"power": 0, "food": 0, "water": 0}

        # Calculate consumption
        net_change["power"] -= sum(POWER_CONSUMPTION_RATE * room.size * room.tier * seconds_passed for room in rooms)
        net_change["food"] -= dweller_count * FOOD_CONSUMPTION_PER_DWELLER * seconds_passed
        net_change["water"] -= dweller_count * WATER_CONSUMPTION_PER_DWELLER * seconds_passed

        # Calculate production
        for room, dwellers in rooms_with_dwellers:
            if not room.output:
                continue

            production_value = int(room.output)
            ability_sum = sum(getattr(dweller, room.ability.lower()) for dweller in dwellers)
            adjusted_production = production_value * ability_sum * seconds_passed

            match room.ability:
                case SPECIALEnum.STRENGTH:
                    net_change["power"] += adjusted_production
                case SPECIALEnum.AGILITY:
                    net_change["food"] += adjusted_production
                case SPECIALEnum.PERCEPTION:
                    net_change["water"] += adjusted_production
                case SPECIALEnum.ENDURANCE:
                    for resource in net_change:
                        net_change[resource] += adjusted_production
                case _:
                    pass

        return VaultUpdate(
            power=round(max(min(vault.power + net_change["power"], vault.power_max), 0)),
            food=round(max(min(vault.food + net_change["food"], vault.food_max), 0)),
            water=round(max(min(vault.water + net_change["water"], vault.water_max), 0)),
        )

    @staticmethod
    async def _get_vault_data(db_session: AsyncSession, vault_id: UUID4):
        """
        Fetch vault data with optimized queries.
        """
        vault_query = select(Vault).where(Vault.id == vault_id)
        vault = (await db_session.exec(vault_query)).first()

        rooms_query = select(Room).where(Room.vault_id == vault_id)
        rooms = (await db_session.exec(rooms_query)).all()

        dweller_count = (
            await db_session.exec(select(func.count(Dweller.id)).where(Dweller.vault_id == vault_id))
        ).first()

        rooms_with_dwellers_query = (
            select(Room, Dweller).join(Dweller, Room.id == Dweller.room_id).where(Room.vault_id == vault_id)
        )
        rooms_with_dwellers_result = (await db_session.exec(rooms_with_dwellers_query)).all()

        rooms_with_dwellers = {}
        for room, dweller in rooms_with_dwellers_result:
            if room.id not in rooms_with_dwellers:
                rooms_with_dwellers[room.id] = (room, [])
            rooms_with_dwellers[room.id][1].append(dweller)

        return vault, rooms, dweller_count, list(rooms_with_dwellers.values())

    async def calculate_resources(self, db_session: AsyncSession, vault_id: UUID4, seconds_passed: int) -> VaultUpdate:
        """
        Calculate the vault's net resource change and return the update.
        """
        vault, rooms, dweller_count, rooms_with_dwellers = await self._get_vault_data(db_session, vault_id)

        return await self._calculate_net_resource_change(
            vault, rooms, dweller_count, rooms_with_dwellers, seconds_passed
        )
