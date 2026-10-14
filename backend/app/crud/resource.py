"""Repository operations for vault resource processing."""

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import UUID4
from sqlalchemy import case, func
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import AgeGroupEnum, DwellerStatusEnum
from app.core.game_config import game_config
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
        vault = (await db_session.execute(select(Vault).where(Vault.id == vault_id))).scalar_one_or_none()
        if vault is None:
            raise ResourceNotFoundException(Vault, identifier=vault_id)

        storage = (await db_session.execute(select(Storage).where(Storage.vault_id == vault_id))).scalar_one_or_none()
        rooms = (await db_session.execute(select(Room).where(Room.vault_id == vault_id))).scalars().all()
        present = (
            Dweller.vault_id == vault_id,
            Dweller.is_deleted.is_(False),
            Dweller.is_dead.is_(False),
            Dweller.status.not_in([DwellerStatusEnum.DEAD, DwellerStatusEnum.EXPLORING, DwellerStatusEnum.QUESTING]),
        )
        dweller_count = (
            await db_session.execute(
                select(
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    Dweller.age_group.in_([AgeGroupEnum.CHILD, AgeGroupEnum.TEEN]),
                                    game_config.breeding.child_consumption_multiplier,
                                ),
                                else_=1.0,
                            )
                        ),
                        0.0,
                    )
                ).where(*present)
            )
        ).scalar_one()
        room_dwellers = (
            await db_session.execute(
                select(Room, Dweller)
                .join(Dweller, Room.id == Dweller.room_id)
                .where(Room.vault_id == vault_id, *present)
                # Production reads the outfit for its SPECIAL bonus, so it must
                # be loaded here. selectinload batches it into one extra query
                # for the whole vault rather than one per dweller per tick.
                # The pet is loaded too: effective_stat also consumes the
                # equipped pet's SPECIAL bonus (B7 eager-load fan-out).
                .options(selectinload(Dweller.outfit), selectinload(Dweller.pet))
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
            game_state=(
                await db_session.execute(select(GameState).where(GameState.vault_id == vault_id))
            ).scalar_one_or_none(),
        )

    @staticmethod
    def save_storage(db_session: AsyncSession, storage: Storage) -> None:
        """Stage a storage change for the caller's transaction."""
        db_session.add(storage)


resource = CRUDResource()
