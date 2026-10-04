"""Dev/QA service for setting up a single youth production apprenticeship."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import UUID4  # ruff: ignore[typing-only-third-party-import]

from app import crud
from app.core.enums import AgeGroupEnum, GenderEnum, RarityEnum
from app.models.base import SPECIALModel
from app.schemas.dweller import DwellerCreate
from app.services.dweller_service import dweller_service
from app.services.training_service import TrainingService


def _now() -> datetime:
    """Return a naive UTC timestamp consistent with persisted game timestamps."""
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class ApprenticeScenarioResult:
    """The active apprentice returned or created by scenario setup."""

    apprentice: Dweller
    room: Room
    created: bool
    ready: bool
    training_duration_seconds: int


@dataclass
class ApprenticeScenarioStatus:
    """A display-ready snapshot of an active apprentice."""

    apprentice: Dweller
    room: Room
    training_duration_seconds: int
    ready: bool


class ApprenticeScenarioService:
    """Opt-in, idempotent builder for testing youth apprenticeship ticks."""

    @staticmethod
    async def find_production_room(db_session: Any, vault_id: UUID4) -> Room:
        """Return a vault production room that trains a SPECIAL ability."""
        room = await crud.room.get_production_with_ability(db_session, vault_id)
        if room is None:
            raise ValueError(f"Vault {vault_id} has no production room with a SPECIAL ability.")
        return room

    @staticmethod
    async def find_active_apprentice(db_session: Any, vault_id: UUID4) -> Dweller | None:
        """Return the existing active apprentice, if the vault already has one."""
        return await crud.dweller.get_first_active_apprentice(db_session, vault_id)

    @staticmethod
    def _training_duration(apprentice: Dweller, room: Room) -> int:
        """Calculate the apprentice's current room-based training duration."""
        if room.ability is None:
            raise ValueError(f"Room {room.id} has no SPECIAL ability.")
        return TrainingService.calculate_training_duration(SPECIALModel.get_stat(apprentice, room.ability), room.tier)

    async def _status_for_apprentice(self, db_session: Any, apprentice: Dweller) -> ApprenticeScenarioStatus:
        if apprentice.room_id is None or apprentice.apprentice_started_at is None:
            raise ValueError(f"Active apprentice {apprentice.id} is missing its room or start time.")
        room = await crud.room.get(db_session, apprentice.room_id)
        duration = self._training_duration(apprentice, room)
        ready = _now() - apprentice.apprentice_started_at >= timedelta(seconds=duration)
        return ApprenticeScenarioStatus(apprentice, room, duration, ready)

    async def setup(self, db_session: Any, vault_id: UUID4, *, ready: bool = False) -> ApprenticeScenarioResult:
        """Reuse an active apprentice or create and assign a teen through real CRUD.

        A production room must already exist; this command never builds rooms or
        changes vault resources. With ``ready=True``, the current apprentice is
        backdated only when needed so repeating the command is idempotent.
        """
        await crud.vault.get(db_session, vault_id)
        production_room = await self.find_production_room(db_session, vault_id)
        apprentice = await self.find_active_apprentice(db_session, vault_id)
        created = apprentice is None

        if apprentice is None:
            apprentice = await dweller_service.create_dweller(
                db_session,
                DwellerCreate(
                    first_name="Apprentice",
                    last_name="Scenario",
                    gender=GenderEnum.FEMALE,
                    rarity=RarityEnum.COMMON,
                    is_adult=False,
                    age_group=AgeGroupEnum.TEEN,
                    birth_date=_now(),
                    vault_id=vault_id,
                ),
            )
            await dweller_service.move_to_room(db_session, apprentice.id, production_room.id)
            await db_session.refresh(apprentice)

        status = await self._status_for_apprentice(db_session, apprentice)
        if ready and not status.ready:
            apprentice.apprentice_started_at = _now() - timedelta(seconds=status.training_duration_seconds + 1)
            db_session.add(apprentice)
            await db_session.commit()
            await db_session.refresh(apprentice)
            status = await self._status_for_apprentice(db_session, apprentice)

        return ApprenticeScenarioResult(
            apprentice=apprentice,
            room=status.room,
            created=created,
            ready=status.ready,
            training_duration_seconds=status.training_duration_seconds,
        )

    async def get_status(self, db_session: Any, vault_id: UUID4) -> ApprenticeScenarioStatus | None:
        """Return the current active apprentice status for a vault, if one exists."""
        apprentice = await self.find_active_apprentice(db_session, vault_id)
        return None if apprentice is None else await self._status_for_apprentice(db_session, apprentice)


apprentice_scenario_service = ApprenticeScenarioService()
