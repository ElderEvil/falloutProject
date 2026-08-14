"""Repository operations for vault resource processing."""

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import UUID4
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Dweller, Room, Storage, Vault
from app.utils.exceptions import ResourceNotFoundException


@dataclass
class VaultResourceData:
    """Persisted data required to calculate one vault resource tick."""

    vault: Vault
    storage: Storage | None
    rooms: Sequence[Room]
    dweller_count: int
    rooms_with_dwellers: list[tuple[Room, list[Dweller]]]


class CRUDResource:
    """Database access used by the resource service."""

    async def get_vault_resource_data(self, db_session: AsyncSession, vault_id: UUID4) -> VaultResourceData:
        vault = (await db_session.execute(select(Vault).where(Vault.id == vault_id))).scalar_one_or_none()
        if vault is None:
            raise ResourceNotFoundException(Vault, identifier=vault_id)

        storage = (await db_session.execute(select(Storage).where(Storage.vault_id == vault_id))).scalar_one_or_none()
        rooms = (await db_session.execute(select(Room).where(Room.vault_id == vault_id))).scalars().all()
        dweller_count = (
            await db_session.execute(select(func.count(Dweller.id)).where(Dweller.vault_id == vault_id))
        ).scalar_one()
        room_dwellers = (
            await db_session.execute(
                select(Room, Dweller).join(Dweller, Room.id == Dweller.room_id).where(Room.vault_id == vault_id)
            )
        ).all()

        grouped_dwellers: dict[UUID4, tuple[Room, list[Dweller]]] = {}
        for room, dweller in room_dwellers:
            grouped_dwellers.setdefault(room.id, (room, []))[1].append(dweller)

        return VaultResourceData(
            vault=vault,
            storage=storage,
            rooms=rooms,
            dweller_count=dweller_count,
            rooms_with_dwellers=list(grouped_dwellers.values()),
        )

    @staticmethod
    def save_storage(db_session: AsyncSession, storage: Storage) -> None:
        """Stage a storage change for the caller's transaction."""
        db_session.add(storage)


resource = CRUDResource()
