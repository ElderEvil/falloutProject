"""Repository operations for vault resource processing."""

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import UUID4
from sqlalchemy import and_
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import AgeGroupEnum, DwellerStatusEnum
from app.core.game_config import game_config
from app.core.tick_profiling import tick_phase
from app.models import Dweller, Room, Storage, Vault
from app.models.game_state import GameState
from app.utils.exceptions import ResourceNotFoundException


@dataclass
class VaultResourceData:
    """Persisted data required to calculate one vault resource tick."""

    vault: Vault
    storage: Storage | None
    rooms: Sequence[Room]
    dweller_count: float
    rooms_with_dwellers: list[tuple[Room, list[Dweller]]]
    game_state: GameState | None = None


class CRUDResource:
    """Database access used by the resource service."""

    async def get_vault_resource_data(self, db_session: AsyncSession, vault_id: UUID4) -> VaultResourceData:
        with tick_phase("resources.load.vault"):
            vault_row = (
                await db_session.execute(
                    select(Vault, Storage, GameState)
                    .select_from(Vault)
                    .outerjoin(Storage, Storage.vault_id == Vault.id)
                    .outerjoin(GameState, GameState.vault_id == Vault.id)
                    .where(Vault.id == vault_id)
                )
            ).one_or_none()
        if vault_row is None:
            raise ResourceNotFoundException(Vault, identifier=vault_id)

        vault, storage, game_state = vault_row
        with tick_phase("resources.load.rooms"):
            rooms = (await db_session.execute(select(Room).where(Room.vault_id == vault_id))).scalars().all()
        present = (
            Dweller.vault_id == vault_id,
            Dweller.is_deleted.is_(False),
            Dweller.is_dead.is_(False),
            Dweller.status.not_in([DwellerStatusEnum.DEAD, DwellerStatusEnum.EXPLORING, DwellerStatusEnum.QUESTING]),
        )
        with tick_phase("resources.load.dwellers"):
            dweller_rows = (
                await db_session.execute(
                    select(Dweller, Room)
                    .select_from(Dweller)
                    .outerjoin(Room, and_(Room.id == Dweller.room_id, Room.vault_id == vault_id))
                    .where(*present)
                    # Production reads the outfit for its SPECIAL bonus, so it must
                    # be loaded here. selectinload batches it into one extra query
                    # for the whole vault rather than one per dweller per tick.
                    # The pet is loaded too: effective_stat also consumes the
                    # equipped pet's SPECIAL bonus (B7 eager-load fan-out).
                    .options(selectinload(Dweller.outfit), selectinload(Dweller.pet))
                )
            ).all()

        dweller_count = 0.0
        grouped_dwellers: dict[UUID4, tuple[Room, list[Dweller]]] = {}
        for dweller, room in dweller_rows:
            dweller_count += (
                game_config.breeding.child_consumption_multiplier
                if dweller.age_group in (AgeGroupEnum.CHILD, AgeGroupEnum.TEEN)
                else 1.0
            )
            if room is not None:
                grouped_dwellers.setdefault(room.id, (room, []))[1].append(dweller)

        return VaultResourceData(
            vault=vault,
            storage=storage,
            rooms=rooms,
            dweller_count=dweller_count,
            rooms_with_dwellers=list(grouped_dwellers.values()),
            game_state=game_state,
        )

    @staticmethod
    def save_storage(db_session: AsyncSession, storage: Storage) -> None:
        """Stage a storage change for the caller's transaction."""
        db_session.add(storage)


resource = CRUDResource()
