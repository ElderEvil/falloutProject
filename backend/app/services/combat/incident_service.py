"""Incident service for managing combat events and vault disasters."""

import logging

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import AgeGroupEnum, DwellerStatusEnum
from app.crud.dweller import dweller as crud_dweller
from app.crud.incident import incident_crud
from app.models.dweller import Dweller
from app.models.game_state import GameState
from app.models.incident import Incident, IncidentStatus, IncidentType, get_incident_definition
from app.schemas.incident import (
    IncidentEventRead,
    IncidentProgress,
    IncidentRead,
    IncidentResponse,
    IncidentRisk,
    IncidentRoundResult,
    PendingIncidentOverflowRead,
)
from app.services.combat import incident_publishing, incident_round, incident_spawning, incident_tick
from app.services.loot_overflow_service import loot_overflow_service
from app.utils.exceptions import AccessDeniedException, ResourceNotFoundException, ValidationException
from app.utils.item_factory import build_junk, build_outfit, build_weapon
from app.utils.static_data import game_data_store

logger = logging.getLogger(__name__)


def _build_held_item(loot_item: dict, storage_id):
    """Rebuild one held incident item for storage, priced the same as its sale."""
    name = loot_overflow_service.item_name(loot_item)
    rarity = str(loot_item.get("rarity", "common"))
    match loot_item.get("item_type", "junk"):
        case "weapon":
            data = next((weapon for weapon in game_data_store.weapons if weapon.name == name), None)
            if data is None:
                raise ValidationException(f"Unknown weapon loot: {name}")
            return build_weapon(data.model_dump(), rarity, storage_id)
        case "outfit":
            data = next((outfit for outfit in game_data_store.outfits if outfit.name == name), None)
            if data is None:
                raise ValidationException(f"Unknown outfit loot: {name}")
            return build_outfit(data.model_dump(), rarity, storage_id)
        case _:
            return build_junk(
                name,
                rarity,
                storage_id,
                value=loot_overflow_service.unit_value_of(loot_item),
                description="Recovered from an incident",
            )


class IncidentService:
    """Service for managing vault incidents and combat."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _record_event(
        db_session: AsyncSession, incident: Incident, kind: str, message: str, data: dict | None = None
    ) -> None:
        """Append a meaningful lifecycle event; callers commit with their state change."""
        incident_publishing.record_event(db_session, incident, kind=kind, message=message, data=data)

    async def get_incident_read(
        self, db_session: AsyncSession, incident: Incident, room_name: str | None
    ) -> IncidentRead:
        """Build the stable, type-aware incident contract consumed by the UI."""
        definition = get_incident_definition(incident.type)
        if incident.type == IncidentType.FIRE:
            progress = IncidentProgress(
                current=min(100, int(incident.combat_progress * 100)), target=100, label=definition.progress_label
            )
        else:
            progress = IncidentProgress(
                current=incident.enemies_defeated,
                target=incident.difficulty * 2,
                label=definition.progress_label,
            )
        events = [
            IncidentEventRead(id=str(event.id), kind=event.kind, message=event.message, data=event.data)
            for event in reversed(await incident_crud.get_recent_events(db_session, incident.id))
        ]
        return IncidentRead(
            id=incident.id,
            vault_id=incident.vault_id,
            room_id=incident.room_id,
            room_name=room_name,
            type=incident.type,
            status=incident.status,
            difficulty=incident.difficulty,
            start_time=incident.start_time.isoformat(),
            end_time=incident.end_time.isoformat() if incident.end_time else None,
            elapsed_time=incident.elapsed_time(),
            duration=incident.duration,
            damage_dealt=incident.damage_dealt,
            enemies_defeated=incident.enemies_defeated,
            rooms_affected=incident.rooms_affected,
            spread_count=incident.spread_count,
            loot=incident.loot,
            unclaimed_loot=incident.unclaimed_loot or [],
            family=definition.family,
            objective=definition.objective,
            progress=progress,
            risk=IncidentRisk(kind=definition.risk_kind, rooms_affected=len(incident.rooms_affected)),
            response=IncidentResponse(label=definition.response_label),
            events=events,
        )

    async def should_spawn_incident(
        self, db_session: AsyncSession, vault_id: UUID4, seconds_passed: int, game_state: GameState | None = None
    ) -> bool:
        """Spawn gating — see incident_spawning."""
        return await incident_spawning.should_spawn_incident(db_session, vault_id, seconds_passed, game_state)

    async def spawn_incident(
        self, db_session: AsyncSession, vault_id: UUID4, incident_type: IncidentType | None = None
    ) -> Incident | None:
        """Spawn orchestration — see incident_spawning."""
        return await incident_spawning.spawn_incident(db_session, vault_id, incident_type)

    async def _no_defender_outcome(self, db_session: AsyncSession, incident: Incident) -> IncidentRoundResult:
        """Round engine — see incident_round."""
        return await incident_round.no_defender_outcome(db_session, incident)

    async def _apply_damage(
        self, db_session: AsyncSession, incident: Incident, dwellers: list[Dweller], damage_to_dwellers: float
    ) -> tuple[int, int, int]:
        """Round engine — see incident_round."""
        return await incident_round.apply_damage(db_session, incident, dwellers, damage_to_dwellers)

    async def _resolve_victory(self, db_session: AsyncSession, incident: Incident, dwellers: list[Dweller]) -> int:
        """Round engine — see incident_round."""
        return await incident_round.resolve_victory(db_session, incident, dwellers)

    async def process_incident(
        self, db_session: AsyncSession, incident: Incident, seconds_passed: int
    ) -> IncidentRoundResult:
        """Round engine — see incident_round."""
        return await incident_round.process_incident(db_session, incident, seconds_passed)

    async def process_vault_incidents(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        seconds_passed: int,
        game_state: GameState | None = None,
    ) -> dict:
        """Per-vault tick orchestration — see incident_tick."""
        return await incident_tick.process_vault_incidents(self, db_session, vault_id, seconds_passed, game_state)

    async def process_all_vaults_incidents(self, db_session: AsyncSession, seconds_passed: int) -> dict:
        """Advisory-locked fan-out across vaults — see incident_tick."""
        return await incident_tick.process_all_vaults_incidents(self, db_session, seconds_passed)

    async def get_incident_for_vault(
        self, db_session: AsyncSession, incident_id: UUID4, vault_id: UUID4, *, for_update: bool = False
    ) -> Incident:
        incident = (
            await incident_crud.get_for_update(db_session, incident_id)
            if for_update
            else await incident_crud.get(db_session, incident_id)
        )
        if not incident:
            raise ResourceNotFoundException(Incident, incident_id)
        if incident.vault_id != vault_id:
            raise AccessDeniedException("Incident does not belong to this vault")
        return incident

    async def get_pending_overflow(
        self, db_session: AsyncSession, vault_id: UUID4
    ) -> list[PendingIncidentOverflowRead]:
        """Resolved incidents still holding loot for a take or sell decision."""
        incidents = await incident_crud.get_resolved_by_vault(db_session, vault_id)
        return [
            PendingIncidentOverflowRead(
                incident_id=incident.id,
                room_id=incident.room_id,
                type=incident.type,
                unclaimed_loot=incident.unclaimed_loot,
            )
            for incident in incidents
            if incident.unclaimed_loot
        ]

    async def take_unclaimed_item(
        self, db_session: AsyncSession, incident_id: UUID4, vault_id: UUID4, index: int
    ) -> list[dict]:
        """Store one held incident item. 409 when storage is still full."""
        incident = await self.get_incident_for_vault(db_session, incident_id, vault_id, for_update=True)
        unclaimed = list(incident.unclaimed_loot or [])
        unclaimed = await loot_overflow_service.settle_take_decision(
            db_session,
            unclaimed,
            index,
            owner=Incident,
            owner_id=incident.id,
            vault_id=incident.vault_id,
            build_row=_build_held_item,
        )
        incident.unclaimed_loot = unclaimed
        db_session.add(incident)
        await db_session.commit()
        return unclaimed

    async def sell_unclaimed_item(
        self, db_session: AsyncSession, incident_id: UUID4, vault_id: UUID4, index: int
    ) -> tuple[int, list[dict]]:
        """Sell one held incident item for caps. Needs no storage space."""
        incident = await self.get_incident_for_vault(db_session, incident_id, vault_id, for_update=True)
        unclaimed = list(incident.unclaimed_loot or [])
        value, unclaimed = await loot_overflow_service.settle_sell_decision(
            db_session, unclaimed, index, owner=Incident, owner_id=incident.id, vault_id=incident.vault_id
        )
        incident.unclaimed_loot = unclaimed
        db_session.add(incident)
        await db_session.commit()
        return value, unclaimed

    async def assign_responders(
        self, db_session: AsyncSession, incident: Incident, dweller_ids: list[UUID4]
    ) -> list[UUID4]:
        """Move eligible dwellers into an active incident room before its next round."""
        if incident.status not in [IncidentStatus.ACTIVE, IncidentStatus.SPREADING]:
            raise ValidationException("Incident is no longer active")

        unique_ids = list(dict.fromkeys(dweller_ids))
        if len(unique_ids) != len(dweller_ids):
            raise ValidationException("Choose each responder only once")

        dwellers = list(await crud_dweller.get_by_ids_in_vault(db_session, unique_ids, incident.vault_id))
        if len(dwellers) != len(unique_ids):
            raise ValidationException("One or more responders do not belong to this vault")

        unavailable = [  # TODO: could be reused, kinda policy - check this one, falls under refactor for me
            dweller
            for dweller in dwellers
            if not dweller.is_adult
            or dweller.age_group != AgeGroupEnum.ADULT
            or dweller.health <= 0
            or dweller.is_dead
            or dweller.status in {DwellerStatusEnum.EXPLORING, DwellerStatusEnum.QUESTING, DwellerStatusEnum.DEAD}
        ]
        if unavailable:
            raise ValidationException("Only healthy adult dwellers in the vault can respond")

        from app.services.dweller_service import dweller_service

        for dweller in dwellers:
            await dweller_service.update_dweller(db_session, dweller.id, {"room_id": incident.room_id})
        self._record_event(db_session, incident, "responders_assigned", f"{len(unique_ids)} responder(s) assigned.")
        await db_session.commit()
        return unique_ids

    async def _spread_incident(self, db_session: AsyncSession, incident: Incident) -> bool:
        """Spread orchestration — see incident_spawning."""
        return await incident_spawning.spread_incident(db_session, incident)

    async def _award_combat_xp(self, db_session: AsyncSession, incident: Incident, dwellers: list[Dweller]) -> None:
        """Round engine — see incident_round."""
        await incident_round.award_combat_xp(db_session, incident, dwellers)


# Global instance
incident_service = IncidentService()
