from collections.abc import Sequence

from pydantic import UUID4
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.game_data_deps import get_static_game_data
from app.crud.base import CRUDBase, ModelType
from app.models import Dweller, Room, Storage
from app.models.vault import Vault
from app.schemas.common import GameStatusEnum, RoomActionEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreateCommonOverride
from app.schemas.room import RoomCreate
from app.schemas.vault import VaultCreate, VaultCreateWithUserID, VaultNumber, VaultReadWithNumbers, VaultUpdate
from app.services.resource_manager import ResourceManager
from app.utils.exceptions import InsufficientResourcesException, ResourceNotFoundException


class CRUDVault(CRUDBase[Vault, VaultCreate, VaultUpdate]):
    def __init__(self, model: type[ModelType]):
        super().__init__(model)
        self.resource_manager = ResourceManager()

    async def get_by_user_id(self, *, db_session: AsyncSession, user_id: UUID4) -> Sequence[Vault]:
        response = await db_session.execute(select(self.model).where(self.model.user_id == user_id))
        return response.scalars().all()

    @staticmethod
    def _calculate_new_capacity(action: RoomActionEnum, current_capacity: int, room_capacity: int) -> int:
        if action in {RoomActionEnum.BUILD, RoomActionEnum.UPGRADE}:
            return current_capacity + room_capacity
        if action == RoomActionEnum.DESTROY:
            return current_capacity - room_capacity
        msg = f"Invalid room action: {action}"
        raise ValueError(msg)

    async def recalculate_vault_attributes(
        self, *, db_session: AsyncSession, vault_obj: Vault, room_obj: Room, action: RoomActionEnum
    ) -> Vault:
        """
        Recalculate the vault attributes based on the newly added or removed room.
        """

        async def _update_vault(vault_update: VaultUpdate):
            await self.update(db_session=db_session, id=vault_obj.id, obj_in=vault_update)

        async def _update_storage(vault_id: UUID4, new_space_max: int):
            response = await db_session.execute(select(Storage).where(Storage.vault_id == vault_id))
            storage_obj = response.scalar_one_or_none()

            if not storage_obj:
                raise ResourceNotFoundException(model=Storage, identifier=vault_id)

            storage_obj.max_space = new_space_max
            db_session.add(storage_obj)
            await db_session.commit()
            await db_session.refresh(storage_obj)

        # Calculate the new vault resource capacity for production rooms
        if room_obj.category == RoomTypeEnum.PRODUCTION and room_obj.capacity is not None:
            match room_obj.ability:
                case "strength":
                    new_capacity = self._calculate_new_capacity(action, vault_obj.power_max, room_obj.capacity)
                    await _update_vault(VaultUpdate(power_max=new_capacity))
                case "agility":
                    new_capacity = self._calculate_new_capacity(action, vault_obj.food_max, room_obj.capacity)
                    await _update_vault(VaultUpdate(food_max=new_capacity))
                case "perception":
                    new_capacity = self._calculate_new_capacity(action, vault_obj.water_max, room_obj.capacity)
                    await _update_vault(VaultUpdate(water_max=new_capacity))
                case _:
                    error_msg = f"Invalid room ability: {room_obj.ability}"
                    raise ValueError(error_msg)

        # Calculate the new vault capacity for capacity rooms
        elif room_obj.category == RoomTypeEnum.CAPACITY:
            match room_obj.name.lower():
                case "living room":
                    new_population_max = self._calculate_new_capacity(
                        action, vault_obj.population_max or 0, room_obj.capacity
                    )
                    await _update_vault(VaultUpdate(population_max=new_population_max))
                case "storage room":
                    # Only process if room has capacity defined
                    if room_obj.capacity is not None:
                        # Query storage to get current max_space (avoid lazy load issue)
                        storage_result = await db_session.execute(
                            select(Storage).where(Storage.vault_id == vault_obj.id)
                        )
                        storage_obj = storage_result.scalars().first()
                        current_max_space = storage_obj.max_space if storage_obj else 0

                        new_storage_space_max = self._calculate_new_capacity(
                            action, current_max_space, room_obj.capacity
                        )
                        await _update_storage(vault_obj.id, new_storage_space_max)
                case _:
                    error_msg = f"Invalid room name: {room_obj.name}"
                    raise ValueError(error_msg)

        return vault_obj

    @staticmethod
    async def get_population(*, db_session: AsyncSession, vault_id: UUID4) -> int:
        count = await db_session.execute(select(func.count(Vault.dwellers)).where(Vault.id == vault_id))
        return count.scalar()

    @staticmethod
    async def get_rooms_count(*, db_session: AsyncSession, vault_id: UUID4) -> int:
        count = await db_session.execute(select(func.count(Vault.rooms)).where(Vault.id == vault_id))
        return count.scalar()

    async def toggle_game_state(self, *, db_session: AsyncSession, vault_id: UUID4) -> Vault:
        vault_obj = await self.get(db_session, id=vault_id)
        new_state = GameStatusEnum.PAUSED if vault_obj.game_state == GameStatusEnum.ACTIVE else GameStatusEnum.ACTIVE
        obj_in = VaultUpdate(game_state=new_state)
        return await self.update(db_session, id=vault_id, obj_in=obj_in)

    async def get_vaults_with_room_and_dweller_count(
        self, *, db_session: AsyncSession, user_id: UUID4
    ) -> list[VaultReadWithNumbers]:
        result = await db_session.execute(
            select(
                self.model,
                func.count(Room.id.distinct()).label("room_count"),
                func.count(Dweller.id.distinct()).label("dweller_count"),
            )
            .select_from(Vault)
            .join(Room, Room.vault_id == self.model.id, isouter=True)
            .join(Dweller, Dweller.vault_id == self.model.id, isouter=True)
            .where(Vault.user_id == user_id)
            .group_by(Vault.id)
        )

        vaults = result.all()
        return [
            VaultReadWithNumbers(
                **vault_obj.model_dump(),
                room_count=room_count,
                dweller_count=dweller_count,
            )
            for vault_obj, room_count, dweller_count in vaults
        ]

    async def get_vault_with_room_and_dweller_count(
        self, *, db_session: AsyncSession, vault_id: UUID4
    ) -> VaultReadWithNumbers:
        result = await db_session.execute(
            select(
                self.model,
                func.count(Room.id.distinct()).label("room_count"),
                func.count(Dweller.id.distinct()).label("dweller_count"),
            )
            .select_from(Vault)
            .join(Room, Room.vault_id == self.model.id, isouter=True)
            .join(Dweller, Dweller.vault_id == self.model.id, isouter=True)
            .where(Vault.id == vault_id)
            .group_by(Vault.id)
        )

        vault_data = result.one()
        vault_obj, room_count, dweller_count = vault_data
        return VaultReadWithNumbers(
            **vault_obj.model_dump(),
            room_count=room_count,
            dweller_count=dweller_count,
        )

    @staticmethod
    async def create_storage(*, db_session: AsyncSession, vault_id: UUID4) -> Storage:
        storage = Storage(vault_id=vault_id)
        db_session.add(storage)
        await db_session.commit()
        return storage

    async def create_with_user_id(
        self, *, db_session: AsyncSession, obj_in: VaultCreate | VaultNumber, user_id: UUID4
    ) -> Vault:
        obj_data = obj_in.model_dump()
        obj_data["user_id"] = user_id
        obj_in = VaultCreateWithUserID(**obj_data)
        return await super().create(db_session, obj_in)

    async def is_enough_dwellers(
        self, *, db_session: AsyncSession, vault_id: UUID4, population_required: int | None
    ) -> bool:
        """
        Check if the vault has enough dwellers to perform an operation.
        """
        if population_required is None:
            return True
        dwellers_count = await self.get_population(db_session=db_session, vault_id=vault_id)
        return dwellers_count >= population_required

    @staticmethod
    async def is_enough_population_space(*, db_session: AsyncSession, vault_id: UUID4, space_required: int) -> bool:
        """
        Check if the vault has enough space to perform an operation.
        """
        result = await db_session.execute(
            select(Vault.population_max, func.count(Dweller.id))
            .select_from(Vault)
            .join(Dweller, Dweller.vault_id == Vault.id)
            .where(Vault.id == vault_id)
            .group_by(Vault.id)
        )
        vault_obj = result.first()
        if not vault_obj:
            error_msg = f"Vault with ID {vault_id} not found"
            raise ValueError(error_msg)
        population_max, current_population = vault_obj
        if population_max is None:
            return False
        return current_population + space_required <= population_max

    async def deposit_caps(self, *, db_session: AsyncSession, vault_obj: Vault, amount: int):
        """Deposit the specified amount to the vault's bottle caps as part of a revenue operation."""
        await self.update(db_session, id=vault_obj.id, obj_in=VaultUpdate(bottle_caps=vault_obj.bottle_caps + amount))

    async def withdraw_caps(self, *, db_session: AsyncSession, vault_obj: Vault, amount: int):
        """Withdraw the specified amount from the vault's bottle caps as part of a spending operation."""
        if vault_obj.bottle_caps < amount:
            amount_needed = amount - vault_obj.bottle_caps
            raise InsufficientResourcesException(resource_name="bottle caps", resource_amount=amount_needed)
        await self.update(db_session, id=vault_obj.id, obj_in=VaultUpdate(bottle_caps=vault_obj.bottle_caps - amount))

    @staticmethod
    def _prepare_room_data(rooms: list[RoomCreate], room_name: str, vault_id: UUID4, x: int, y: int) -> dict:
        from app.crud.room import room as room_crud  # noqa: PLC0415

        room_data = next(room for room in rooms if room.name.lower() == room_name)
        room_data_dict = room_data.model_dump()

        # Evaluate capacity and output formulas if present
        size = room_data.size_min
        tier = 1  # Initial tier

        # Check in the dumped dict for formula fields
        if room_data_dict.get("capacity_formula"):
            room_data_dict["capacity"] = room_crud.evaluate_capacity_formula(
                room_data_dict["capacity_formula"], tier, size
            )
        if room_data_dict.get("output_formula"):
            room_data_dict["output"] = room_crud.evaluate_output_formula(room_data_dict["output_formula"], tier, size)

        room_data_dict.update(
            {
                "vault_id": vault_id,
                "size": size,
                "coordinate_x": x,
                "coordinate_y": y,
            }
        )
        return room_data_dict

    async def initiate(self, *, db_session: AsyncSession, obj_in: VaultNumber, user_id: UUID4) -> Vault:
        """
        Create a new vault for a user and initialize it with essential rooms and dwellers.
        Includes:
        - Vault door and elevators (infrastructure)
        - Production rooms (power generator, diner, water treatment) with assigned dwellers
        - Storage room
        - 6 dwellers with boosted SPECIAL stats assigned to production rooms
        """
        vault_db_obj = await self.create_with_user_id(db_session=db_session, obj_in=obj_in, user_id=user_id)

        # Create storage
        await self.create_storage(db_session=db_session, vault_id=vault_db_obj.id)

        # Refresh vault to load storage relationship
        await db_session.refresh(vault_db_obj)

        game_data_store = get_static_game_data()
        rooms = game_data_store.rooms

        # Infrastructure rooms (existing)
        vault_door_data = self._prepare_room_data(rooms, "vault door", vault_db_obj.id, 0, 0)
        elevators_data = [self._prepare_room_data(rooms, "elevator", vault_db_obj.id, 0, y) for y in range(1, 4)]

        # Production rooms (new)
        power_generator_data = self._prepare_room_data(rooms, "power generator", vault_db_obj.id, 1, 1)
        diner_data = self._prepare_room_data(rooms, "diner", vault_db_obj.id, 1, 2)
        water_treatment_data = self._prepare_room_data(rooms, "water treatment", vault_db_obj.id, 1, 3)
        storage_room_data = self._prepare_room_data(rooms, "storage room", vault_db_obj.id, 1, 4)

        infrastructure_rooms = [RoomCreate(**vault_door_data)] + [RoomCreate(**data) for data in elevators_data]
        production_rooms = [
            RoomCreate(**power_generator_data),
            RoomCreate(**diner_data),
            RoomCreate(**water_treatment_data),
            RoomCreate(**storage_room_data),
        ]

        from app.crud.room import room as room_crud  # noqa: PLC0415

        # Create infrastructure rooms (don't affect vault capacity)
        await room_crud.create_all(db_session, infrastructure_rooms)

        # Create production rooms and update vault capacities
        created_production_rooms = []
        for room_create in production_rooms:
            room_obj = await room_crud.create(db_session, room_create)
            created_production_rooms.append(room_obj)
            # Recalculate vault attributes after each room
            vault_db_obj = await self.recalculate_vault_attributes(
                db_session=db_session, vault_obj=vault_db_obj, room_obj=room_obj, action=RoomActionEnum.BUILD
            )

        # Refresh vault to get updated capacities
        await db_session.refresh(vault_db_obj)

        # Set initial resources to 50% of max capacity
        initial_power = vault_db_obj.power_max // 2
        initial_food = vault_db_obj.food_max // 2
        initial_water = vault_db_obj.water_max // 2

        vault_db_obj = await self.update(
            db_session=db_session,
            id=vault_db_obj.id,
            obj_in=VaultUpdate(power=initial_power, food=initial_food, water=initial_water),
        )

        # Create dwellers with boosted SPECIAL stats
        import logging  # noqa: PLC0415

        from app.crud.dweller import dweller as dweller_crud  # noqa: PLC0415
        from app.schemas.dweller import DwellerUpdate  # noqa: PLC0415

        logger = logging.getLogger(__name__)

        # 2 dwellers for each production room (Strength, Agility, Perception)
        dweller_specs = [
            (SPECIALEnum.STRENGTH, created_production_rooms[0].id),  # Power Generator
            (SPECIALEnum.STRENGTH, created_production_rooms[0].id),
            (SPECIALEnum.AGILITY, created_production_rooms[1].id),  # Diner
            (SPECIALEnum.AGILITY, created_production_rooms[1].id),
            (SPECIALEnum.PERCEPTION, created_production_rooms[2].id),  # Water Treatment
            (SPECIALEnum.PERCEPTION, created_production_rooms[2].id),
        ]

        try:
            for i, (special_stat, room_id) in enumerate(dweller_specs):
                logger.info(f"Creating dweller {i + 1}/6 with {special_stat} for room {room_id}")  # noqa: G004
                obj_in = DwellerCreateCommonOverride(special_boost=special_stat)
                dweller_obj = await dweller_crud.create_random(db_session, vault_db_obj.id, obj_in=obj_in)
                logger.info(f"Created dweller {dweller_obj.id}, assigning to room {room_id}")  # noqa: G004
                # Assign dweller to room
                await dweller_crud.update(
                    db_session=db_session, id=dweller_obj.id, obj_in=DwellerUpdate(room_id=room_id)
                )
                logger.info(f"Dweller {dweller_obj.id} assigned to room {room_id}")  # noqa: G004
        except Exception as e:
            logger.error(f"Failed to create dwellers: {e}", exc_info=True)  # noqa: G004, G201
            raise

        return vault_db_obj

    async def update_resources(self, db_session: AsyncSession, vault_id: UUID4):
        updated_resources, _events = await self.resource_manager.process_vault_resources(
            db_session=db_session, vault_id=vault_id, seconds_passed=60
        )

        return await self.update(db_session=db_session, id=vault_id, obj_in=updated_resources)


vault = CRUDVault(Vault)
