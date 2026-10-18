"""Incident service for managing combat events and vault disasters."""

import logging

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import DwellerStatusEnum
from app.core.event_bus import GameEvent, event_bus
from app.crud.dweller import dweller as crud_dweller
from app.crud.incident import incident_crud
from app.crud.room import room as room_crud
from app.crud.team import team_crud
from app.models.dweller import Dweller
from app.models.game_state import GameState
from app.models.incident import (
    Incident,
    IncidentObjective,
    IncidentStatus,
    IncidentType,
    get_incident_definition,
)
from app.models.team import COMMITTED_MEMBER_STATUSES
from app.schemas.incident import (
    IncidentEventRead,
    IncidentListItem,
    IncidentListResponse,
    IncidentProgress,
    IncidentRead,
    IncidentResponderRead,
    IncidentResponse,
    IncidentRisk,
    IncidentRoundResult,
    PendingIncidentOverflowRead,
)
from app.services.combat import incident_publishing, incident_round, incident_spawning, incident_tick
from app.services.loot_overflow_service import loot_overflow_service
from app.utils.dweller_availability import availability_error
from app.utils.exceptions import AccessDeniedException, ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)

#: Maximum arriving helpers, in addition to the affected room's residents.
MAX_INCIDENT_RESPONDERS = 6


async def committed_responder_ids(
    db_session: AsyncSession, vault_id: UUID4, *, exclude_incident_id: UUID4 | None = None
) -> set[UUID4]:
    """Dweller ids rostered on another ACTIVE incident and therefore unavailable.

    Room residents defend automatically and cannot be pulled to another incident.
    A dweller holding an ``assigned`` or ``dispatched`` slot on any live incident
    other than ``exclude_incident_id`` is already committed to that response and
    must not be drafted again; ``completed`` members are free.
    """
    committed: set[UUID4] = set()
    for incident in await incident_crud.get_active_by_vault(db_session, vault_id):
        if exclude_incident_id is not None and incident.id == exclude_incident_id:
            continue
        committed.update(
            dweller.id for dweller in await crud_dweller.get_healthy_adults_in_room(db_session, incident.room_id)
        )
        members = await team_crud.get_incident_team(db_session, incident.id, vault_id)
        committed.update(member.dweller_id for member in members if member.status in COMMITTED_MEMBER_STATUSES)
    return committed


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

    async def _room_name(self, db_session: AsyncSession, room_id: UUID4 | None) -> str | None:
        """Resolve a room's display name; None when the room is gone."""
        if room_id is None:
            return None
        names = await room_crud.get_names_by_ids(db_session, [room_id])
        return names.get(room_id)

    async def get_active_incident_list(self, db_session: AsyncSession, vault_id: UUID4) -> IncidentListResponse:
        """Build the active-incident list contract for a vault."""
        incidents = await incident_crud.get_active_by_vault(db_session, vault_id)
        room_names = await room_crud.get_names_by_ids(db_session, [incident.room_id for incident in incidents])

        return IncidentListResponse(
            vault_id=str(vault_id),
            incident_count=len(incidents),
            incidents=[
                IncidentListItem(
                    id=str(incident.id),
                    type=incident.type,
                    status=incident.status,
                    room_id=str(incident.room_id),
                    room_name=room_names.get(incident.room_id),
                    difficulty=incident.difficulty,
                    start_time=incident.start_time.isoformat(),
                    elapsed_time=incident.elapsed_time(),
                    damage_dealt=incident.damage_dealt,
                    enemies_defeated=incident.enemies_defeated,
                )
                for incident in incidents
            ],
        )

    async def get_incident_read_for_vault(
        self, db_session: AsyncSession, vault_id: UUID4, incident_id: UUID4
    ) -> IncidentRead:
        """Get an incident's read contract, scoped to the vault that owns it.

        Raises:
            ResourceNotFoundException: If the incident does not exist in this vault.
        """
        incident = await incident_crud.get(db_session, incident_id)
        if not incident or incident.vault_id != vault_id:
            raise ResourceNotFoundException(model=Incident, identifier=incident_id)

        return await self.get_incident_read(db_session, incident, await self._room_name(db_session, incident.room_id))

    async def get_incident_read(
        self, db_session: AsyncSession, incident: Incident, room_name: str | None
    ) -> IncidentRead:
        """Build the stable, type-aware incident contract consumed by the UI."""
        definition = get_incident_definition(incident.type)
        if definition.objective == IncidentObjective.CONTAIN:
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
            junk_description="Recovered from an incident",
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
        if value > 0:
            await event_bus.emit(
                GameEvent.RESOURCE_COLLECTED, incident.vault_id, {"resource_type": "caps", "amount": value}
            )
        return value, unclaimed

    async def assign_responders(
        self, db_session: AsyncSession, incident: Incident, dweller_ids: list[UUID4]
    ) -> list[UUID4]:
        """Move eligible dwellers into an active incident room before its next round.

        Records the incident's designated responder team; room presence continues
        to drive the per-round combat engine. The roster is the set of responders
        sent for the incident — assignments append, never replace, so the persisted
        roster cannot diverge from the responders actually sent into the room.

        The incident row is re-loaded FOR UPDATE so the roster read, the six-responder
        cap check, and the insert all run under one row lock: two concurrent
        assignments cannot both pass the cap check and exceed six members.
        """
        if incident.status not in [IncidentStatus.ACTIVE, IncidentStatus.SPREADING]:
            raise ValidationException("Incident is no longer active")

        # Re-load under a FOR UPDATE row lock so the read→check→insert below is
        # serialized against concurrent assignments to the same incident.
        locked_incident = await incident_crud.get_for_update(db_session, incident.id)
        if locked_incident is None:
            raise ResourceNotFoundException(Incident, incident.id)
        incident = locked_incident
        if incident.status not in [IncidentStatus.ACTIVE, IncidentStatus.SPREADING]:
            raise ValidationException("Incident is no longer active")

        unique_ids = list(dict.fromkeys(dweller_ids))
        if not unique_ids:
            raise ValidationException("Choose at least one responder")
        if len(unique_ids) != len(dweller_ids):
            raise ValidationException("Choose each responder only once")

        dwellers = list(await crud_dweller.get_by_ids_in_vault(db_session, unique_ids, incident.vault_id))
        if len(dwellers) != len(unique_ids):
            raise ValidationException("One or more responders do not belong to this vault")

        unavailable = [
            dweller
            for dweller in dwellers
            if availability_error(dweller, require_healthy=True) or dweller.status == DwellerStatusEnum.FIGHTING
        ]
        if unavailable:
            raise ValidationException("Only healthy adult dwellers in the vault can respond")

        committed_ids = await committed_responder_ids(db_session, incident.vault_id, exclude_incident_id=incident.id)
        skipped = [dweller for dweller in dwellers if dweller.id in committed_ids]
        eligible = [dweller for dweller in dwellers if dweller.id not in committed_ids]
        if not eligible:
            raise ValidationException("All chosen responders are already committed to another active incident")

        existing_members = await team_crud.get_incident_team(db_session, incident.id, incident.vault_id)
        existing_member_ids = {member.dweller_id for member in existing_members}
        # Residents already defend through room presence; only arrivals consume
        # helper slots or need an origin posting for the return pass.
        residents = [
            dweller
            for dweller in eligible
            if dweller.room_id == incident.room_id and dweller.id not in existing_member_ids
        ]
        resident_ids = {dweller.id for dweller in residents}
        eligible = [dweller for dweller in eligible if dweller.id not in resident_ids]
        skipped.extend(residents)
        if not eligible:
            raise ValidationException("Chosen dwellers are already defending this room")
        eligible_ids = [dweller.id for dweller in eligible]
        if len(existing_member_ids | set(eligible_ids)) > MAX_INCIDENT_RESPONDERS:
            raise ValidationException("An incident team holds at most 6 responders")

        origins = {dweller.id: dweller.room_id for dweller in eligible}
        members = await team_crud.add_incident_team_members(db_session, incident.id, incident.vault_id, eligible_ids)
        for member in members:
            member.origin_room_id = origins[member.dweller_id]
            db_session.add(member)

        from app.services.dweller_service import dweller_service

        for dweller in eligible:
            await dweller_service.update_dweller(db_session, dweller.id, {"room_id": incident.room_id})
        self._record_event(
            db_session,
            incident,
            "responders_assigned",
            f"{len(eligible_ids)} responder(s) assigned.",
            data={"skipped": [dweller.first_name for dweller in skipped]} if skipped else None,
        )
        await db_session.commit()
        return eligible_ids

    async def get_incident_team_read(
        self, db_session: AsyncSession, incident_id: UUID4, vault_id: UUID4
    ) -> list[IncidentResponderRead]:
        """The vault's designated responder roster for an incident, as read shapes."""
        incident = await self.get_incident_for_vault(db_session, incident_id, vault_id)
        members = await team_crud.get_incident_team(db_session, incident.id, incident.vault_id)
        return [
            IncidentResponderRead(
                id=member.id,
                team_id=member.team_id,
                dweller_id=member.dweller_id,
                slot_number=member.slot_number,
                status=member.status,
                origin_room_id=member.origin_room_id,
                created_at=member.created_at,
                updated_at=member.updated_at,
            )
            for member in members
        ]

    async def _spread_incident(self, db_session: AsyncSession, incident: Incident) -> bool:
        """Spread orchestration — see incident_spawning."""
        return await incident_spawning.spread_incident(db_session, incident)

    async def _award_combat_xp(self, db_session: AsyncSession, incident: Incident, dwellers: list[Dweller]) -> None:
        """Round engine — see incident_round."""
        await incident_round.award_combat_xp(db_session, incident, dwellers)


# Global instance
incident_service = IncidentService()
