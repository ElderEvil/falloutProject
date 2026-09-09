from collections.abc import Sequence
from logging import getLogger

from pydantic import UUID4
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import GameStatusEnum, RoomActionEnum
from app.crud.base import CRUDBase
from app.models import Dweller, Room, Storage
from app.models.game_state import GameState
from app.models.vault import Vault
from app.schemas.vault import VaultCreate, VaultCreateWithUserID, VaultNumber, VaultReadWithNumbers, VaultUpdate
from app.utils.resource_warnings import get_resource_warnings

logger = getLogger(__name__)


class CRUDVault(CRUDBase[Vault, VaultCreate, VaultUpdate]):
    async def get_by_user_id(
        self, *, db_session: AsyncSession, user_id: UUID4, include_deleted: bool = False
    ) -> Sequence[Vault]:
        query = select(self.model).where(self.model.user_id == user_id)
        if not include_deleted:
            query = query.where(~self.model.is_deleted)
        response = await db_session.execute(query)
        return response.scalars().all()

    async def recalculate_vault_attributes(
        self, *, db_session: AsyncSession, vault_obj: Vault, room_obj: Room, action: RoomActionEnum
    ) -> Vault:
        """Legacy entry point; canonical logic lives in VaultService."""
        from app.services.vault_service import vault_service

        return await vault_service.recalculate_vault_attributes(
            db_session=db_session, vault_obj=vault_obj, room_obj=room_obj, action=action
        )

    async def update_storage(self, db_session: AsyncSession, vault_id: UUID4, new_space_max: int) -> Storage:
        """Update the storage max space for a vault (delegates to storage CRUD)."""
        from app.crud.storage import storage as storage_crud

        return await storage_crud.set_max_space(db_session, vault_id, new_space_max)

    async def increase_storage_space(self, db_session: AsyncSession, vault_id: UUID4, amount: int) -> Storage:
        """Increase a vault's storage capacity by a room's capacity."""
        from app.crud.storage import storage as storage_crud

        return await storage_crud.adjust_max_space(db_session, vault_id, amount)

    @staticmethod
    async def get_population(*, db_session: AsyncSession, vault_id: UUID4) -> int:
        count = await db_session.execute(select(func.count(Vault.dwellers)).where(Vault.id == vault_id))
        return count.scalar()

    @staticmethod
    async def get_rooms_count(*, db_session: AsyncSession, vault_id: UUID4) -> int:
        count = await db_session.execute(select(func.count(Vault.rooms)).where(Vault.id == vault_id))
        return count.scalar()

    @staticmethod
    async def get_population_max(*, db_session: AsyncSession, vault_id: UUID4) -> int | None:
        """Population cap, or None when the vault is missing (treated as unbounded by callers)."""
        result = await db_session.execute(select(Vault.population_max).where(Vault.id == vault_id))
        return result.scalar_one_or_none()

    async def get_population_space(self, *, db_session: AsyncSession, vault_id: UUID4) -> tuple[int | None, int]:
        """Population cap with assigned-dweller count; (None, 0) when the vault is missing."""
        result = await db_session.execute(
            select(Vault.population_max, func.count(Dweller.id))
            .select_from(Vault)
            .join(Dweller, Dweller.vault_id == Vault.id)
            .where(Vault.id == vault_id)
            .where(Dweller.room_id.is_not(None))
            .group_by(Vault.id)
        )
        row = result.first()
        if row:
            return (row[0], row[1])
        vault_check = await db_session.execute(select(Vault.population_max).where(Vault.id == vault_id))
        return (vault_check.scalar_one_or_none(), 0)

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
                func.coalesce(func.max(Storage.stimpack), 0).label("stimpack"),
                func.coalesce(func.max(Storage.radaway), 0).label("radaway"),
            )
            .select_from(Vault)
            .join(Room, Room.vault_id == self.model.id, isouter=True)
            .join(Dweller, Dweller.vault_id == self.model.id, isouter=True)
            .join(Storage, Storage.vault_id == self.model.id, isouter=True)
            .where(Vault.user_id == user_id)
            .where(Vault.deleted_at.is_(None))
            .group_by(Vault.id)
        )

        vaults = result.all()
        return [
            VaultReadWithNumbers(
                **vault_obj.model_dump(),
                room_count=room_count,
                dweller_count=dweller_count,
                stimpack=stimpack,
                radaway=radaway,
                resource_warnings=get_resource_warnings(
                    vault_obj,
                    {
                        "power": float(vault_obj.power),
                        "food": float(vault_obj.food),
                        "water": float(vault_obj.water),
                    },
                ),
            )
            for vault_obj, room_count, dweller_count, stimpack, radaway in vaults
        ]

    async def get_vault_with_room_and_dweller_count(
        self, *, db_session: AsyncSession, vault_id: UUID4
    ) -> VaultReadWithNumbers:
        result = await db_session.execute(
            select(
                self.model,
                func.count(Room.id.distinct()).label("room_count"),
                func.count(Dweller.id.distinct()).label("dweller_count"),
                func.coalesce(func.max(Storage.stimpack), 0).label("stimpack"),
                func.coalesce(func.max(Storage.radaway), 0).label("radaway"),
            )
            .select_from(Vault)
            .join(Room, Room.vault_id == self.model.id, isouter=True)
            .join(Dweller, Dweller.vault_id == self.model.id, isouter=True)
            .join(Storage, Storage.vault_id == self.model.id, isouter=True)
            .where(Vault.id == vault_id)
            .group_by(Vault.id)
        )

        vault_data = result.one()
        vault_obj, room_count, dweller_count, stimpack, radaway = vault_data
        return VaultReadWithNumbers(
            **vault_obj.model_dump(),
            room_count=room_count,
            dweller_count=dweller_count,
            stimpack=stimpack,
            radaway=radaway,
            resource_warnings=get_resource_warnings(
                vault_obj,
                {
                    "power": float(vault_obj.power),
                    "food": float(vault_obj.food),
                    "water": float(vault_obj.water),
                },
            ),
        )

    @staticmethod
    async def create_storage(*, db_session: AsyncSession, vault_id: UUID4) -> Storage:
        """Create the storage row for a vault (delegates to storage CRUD)."""
        from app.crud.storage import storage as storage_crud

        return await storage_crud.create_for_vault(db_session=db_session, vault_id=vault_id)

    async def create_with_user_id(
        self, *, db_session: AsyncSession, obj_in: VaultCreate | VaultNumber | dict, user_id: UUID4
    ) -> Vault:
        obj_data = obj_in.model_dump() if hasattr(obj_in, "model_dump") else obj_in
        obj_data["user_id"] = user_id
        obj_in = VaultCreateWithUserID(**obj_data)
        return await super().create(db_session, obj_in)

    async def is_enough_dwellers(
        self, *, db_session: AsyncSession, vault_id: UUID4, population_required: int | None
    ) -> bool:
        """Legacy entry point; canonical logic lives in VaultService."""
        from app.services.vault_service import vault_service

        return await vault_service.is_enough_dwellers(
            db_session=db_session, vault_id=vault_id, population_required=population_required
        )

    @staticmethod
    async def is_enough_population_space(*, db_session: AsyncSession, vault_id: UUID4, space_required: int) -> bool:
        """Legacy entry point; canonical logic lives in VaultService."""
        from app.services.vault_service import vault_service

        return await vault_service.is_enough_population_space(
            db_session=db_session, vault_id=vault_id, space_required=space_required
        )

    async def deposit_caps(
        self,
        *,
        db_session: AsyncSession,
        vault_obj: Vault,
        amount: int,
        commit: bool = True,
        emit_event: bool = True,
        track_earnings: bool = True,
    ) -> None:
        """Legacy entry point; canonical logic lives in VaultService."""
        from app.services.vault_service import vault_service

        await vault_service.deposit_caps(
            db_session=db_session,
            vault_obj=vault_obj,
            amount=amount,
            commit=commit,
            emit_event=emit_event,
            track_earnings=track_earnings,
        )

    async def withdraw_caps(self, *, db_session: AsyncSession, vault_obj: Vault, amount: int):
        """Legacy entry point; canonical logic lives in VaultService."""
        from app.services.vault_service import vault_service

        await vault_service.withdraw_caps(db_session=db_session, vault_obj=vault_obj, amount=amount)

    async def delete(self, db_session: AsyncSession, id: UUID4, soft: bool = True) -> Vault:
        """Delete vault and its associated gamestate."""
        # First, delete the associated gamestate if it exists
        result = await db_session.execute(select(GameState).where(GameState.vault_id == id))
        gamestate = result.scalar_one_or_none()
        if gamestate:
            await db_session.delete(gamestate)
            await db_session.commit()

        # Now delete the vault using the base class method with soft parameter
        return await super().delete(db_session, id, soft=soft)


vault = CRUDVault(Vault)
