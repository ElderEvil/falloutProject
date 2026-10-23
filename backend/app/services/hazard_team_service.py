"""Earned hazard teams: service turns into a place on a standing team."""

import logging
from dataclasses import dataclass

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import db_locks
from app.core.enums import HazardTeam, RoomTypeEnum
from app.crud import outfit as outfit_crud
from app.crud.dweller import dweller as crud_dweller
from app.crud.incident_participant import incident_participant_crud
from app.crud.room import room as crud_room
from app.crud.storage import storage as crud_storage
from app.crud.team import team_crud
from app.models.dweller import Dweller
from app.models.incident import HAZARD_TEAM_INCIDENT_TYPES, Incident, hazard_team_for
from app.models.outfit import Outfit
from app.models.team import ACTIVE_STATUS, COMMITTED_MEMBER_STATUSES, DISPATCHED_STATUS, RESERVE_STATUS, TeamMember
from app.schemas.contamination_team import ContaminationTeamRead, HazardTeamMemberRead, HazardTeamRosterRead
from app.services.bio_service import bio_service
from app.services.notification_service import notification_service
from app.utils.dweller_availability import availability_error, is_incident_responder_available
from app.utils.exceptions import (
    ContentNoChangeException,
    ResourceConflictException,
    ResourceNotFoundException,
    ValidationException,
)
from app.utils.hazard_resist import outfit_fire_resist, outfit_radiation_resist

logger = logging.getLogger(__name__)

#: Incident participations required before a dweller earns a place on a team.
QUALIFYING_INCIDENTS = 3
#: Dwellers who hold a team; further qualifiers wait on the bench.
TEAM_SIZE = 3
#: Bio entry source for service milestones (declared in ``bio_service.BIO_SECTIONS``).
BIO_SOURCE = "hazard"
#: How each team reads in a dweller's biography.
TEAM_LABELS: dict[HazardTeam, str] = {
    HazardTeam.FIRE: "fire team",
    HazardTeam.RADIATION: "radiation team",
}
#: Response-power multiplier per active matching member during a hazard incident.
TEAM_RESPONSE_BONUS = 0.20
#: Additional damage/radiation reduction for active matching members.
TEAM_HAZARD_RESIST = 0.20
#: Outfit an active member is auto-equipped with when one is spare.
TEAM_OUTFIT_NAMES: dict[HazardTeam, str] = {
    HazardTeam.FIRE: "Firefighter suit",
    HazardTeam.RADIATION: "Hazmat suit",
}


def roster_lock_key(vault_id: UUID4, team: HazardTeam) -> str:
    """Advisory-lock key guarding one vault's hazard roster against concurrent mutation."""
    return f"hazard-team:{vault_id}:{team.value}"


@dataclass
class HazardTeamRoundResult:
    """What one incident round changed on a hazard team.

    ``new_places`` lists every place earned this round (active or bench);
    ``active_gainers`` are the dwellers who now hold an ACTIVE place as a
    result of this round — join-as-active plus bench promotions — so callers
    can notify and auto-equip exactly the members who stepped up.
    ``active_ids`` are the present dwellers holding an active place on the
    matching team, so callers apply the response bonus without re-querying.
    """

    new_places: list[TeamMember]
    active_gainers: list[Dweller]
    active_ids: frozenset[UUID4] = frozenset()


class HazardTeamService:
    """Turns incident participation into earned places and bio milestones."""

    async def record_participation(
        self, db_session: AsyncSession, incident: Incident, dwellers: list[Dweller]
    ) -> HazardTeamRoundResult:
        """Credit this round's defenders and promote anyone who just qualified.

        Called inside the incident round, so everything written here rides the
        round's single commit and a failed round leaves no trace. Returns the
        round's team changes so the caller can notify and auto-equip post-commit.
        """
        if not dwellers:
            return HazardTeamRoundResult(new_places=[], active_gainers=[])
        credited_ids = await incident_participant_crud.record(
            db_session, incident.id, [dweller.id for dweller in dwellers]
        )
        team = hazard_team_for(incident.type)
        if not team:
            return HazardTeamRoundResult(new_places=[], active_gainers=[])
        dwellers_by_id = {dweller.id: dweller for dweller in dwellers}
        new_places: list[TeamMember] = []
        active_gainers: list[Dweller] = []

        # Roster places are read-then-insert, so two workers could both pass the read and
        # then collide on uq_team_vault_hazard / uq_team_member_slot. A transaction-scoped
        # lock keyed by the roster serializes the mutation until this round commits — the
        # credit recorded above is untouched, so a deferred place is simply earned next round.
        if await db_locks.try_advisory_xact_lock(db_session, roster_lock_key(incident.vault_id, team)):
            # Bench members step up first so seniority holds and a freed place is
            # never handed to the newest arrival.
            promoted = await self._promote_bench(db_session, incident.vault_id, team, dwellers_by_id)
            promoted_ids = {place.dweller_id for place, _ in promoted}
            new_places = [place for place, _ in promoted]
            active_gainers = [dweller for _, dweller in promoted]
            for dweller_id in credited_ids:
                dweller = dwellers_by_id.get(dweller_id)
                if dweller is None:
                    continue
                place = await self._join_if_qualified(db_session, incident.vault_id, dweller, team)
                if place is None:
                    continue
                new_places.append(place)
                if place.status == ACTIVE_STATUS:
                    active_gainers.append(dweller)
            await self._announce_places(db_session, incident.vault_id, team, new_places, promoted_ids, dwellers_by_id)
        else:
            logger.info(
                "Hazard roster %s busy for vault %s; deferring the place to the next round",
                team.value,
                incident.vault_id,
            )
        active_ids = frozenset(
            await team_crud.get_active_hazard_member_ids(db_session, incident.vault_id, team, [d.id for d in dwellers])
        )
        return HazardTeamRoundResult(new_places=new_places, active_gainers=active_gainers, active_ids=active_ids)

    async def _has_response_station(self, db_session: AsyncSession, vault_id: UUID4) -> bool:
        """Whether the vault has built its Response Station — the gate on team formation."""
        return bool(await crud_room.get_by_category(db_session, vault_id, RoomTypeEnum.RESPONSE))

    async def _active_responders(self, db_session: AsyncSession, vault_id: UUID4) -> int:
        return sum([await team_crud.count_active_hazard(db_session, vault_id, team) for team in HazardTeam])

    async def _has_response_capacity(self, db_session: AsyncSession, vault_id: UUID4) -> bool:
        stations = await crud_room.get_by_category(db_session, vault_id, RoomTypeEnum.RESPONSE)
        if not stations:
            return False
        station = stations[0]
        capacity = station.capacity if station.capacity is not None else (station.size or 3)
        return await self._active_responders(db_session, vault_id) < capacity

    async def _join_if_qualified(
        self, db_session: AsyncSession, vault_id: UUID4, dweller: Dweller, team: HazardTeam
    ) -> TeamMember | None:
        # Formation gating: no station, no team to join. The participation credit already
        # stands, so a place is earned on a later callout once the station is built.
        if not await self._has_response_station(db_session, vault_id):
            return None
        if await team_crud.get_hazard_member(db_session, vault_id, team, dweller.id):
            return None
        fought = await incident_participant_crud.count_incidents(
            db_session, dweller.id, HAZARD_TEAM_INCIDENT_TYPES[team]
        )
        if fought < QUALIFYING_INCIDENTS:
            return None
        active = await team_crud.count_active_hazard(db_session, vault_id, team)
        has_room = await self._has_response_capacity(db_session, vault_id)
        status = ACTIVE_STATUS if active < TEAM_SIZE and has_room else RESERVE_STATUS
        team_row = await team_crud.get_or_create_hazard_team(db_session, vault_id, team)
        slot_number = await self._next_free_slot(db_session, vault_id, team) if status == ACTIVE_STATUS else None
        place = TeamMember(team_id=team_row.id, dweller_id=dweller.id, status=status, slot_number=slot_number)
        await team_crud.add_member(db_session, place)
        self._record_bio_entry(dweller, team, status, fought)
        logger.info(f"{dweller.first_name} {dweller.last_name} joined the {TEAM_LABELS[team]} as {status}")
        return place

    async def _next_free_slot(self, db_session: AsyncSession, vault_id: UUID4, team: HazardTeam) -> int | None:
        """The lowest unheld slot number (1-3) on the team, or None when full."""
        await team_crud.free_dead_hazard_slots(db_session, vault_id, team)
        active = await team_crud.get_hazard_team(db_session, vault_id, team)
        taken = {
            place.slot_number for place in active if place.status == ACTIVE_STATUS and place.slot_number is not None
        }
        return next((slot for slot in (1, 2, 3) if slot not in taken), None)

    def _record_bio_entry(self, dweller: Dweller, team: HazardTeam, status: str, fought: int) -> None:
        label = TEAM_LABELS[team]
        callouts = f"{fought} {'callout' if fought == 1 else 'callouts'}"
        text = (
            f"Took a place on the vault's {label} after {callouts}."
            if status == ACTIVE_STATUS
            else f"Earned a bench place on the vault's {label} after {callouts}."
        )
        bio_service.add_entry(dweller, BIO_SOURCE, text, {"team": team.value, "status": status})

    async def _promote_bench(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        team: HazardTeam,
        dwellers_by_id: dict[UUID4, Dweller],
    ) -> list[tuple[TeamMember, Dweller]]:
        """Step the most senior bench members into any places a loss freed."""
        if not await self._has_response_station(db_session, vault_id):
            return []
        vacancies = TEAM_SIZE - await team_crud.count_active_hazard(db_session, vault_id, team)
        promoted: list[TeamMember] = []
        for place in await team_crud.get_hazard_reserve(db_session, vault_id, team):
            if vacancies <= 0:
                break
            place.status = ACTIVE_STATUS
            place.slot_number = await self._next_free_slot(db_session, vault_id, team)
            db_session.add(place)
            await db_session.flush()
            promoted.append(place)
            vacancies -= 1
        missing_ids: list[UUID4 | str] = [
            place.dweller_id for place in promoted if place.dweller_id not in dwellers_by_id
        ]
        if missing_ids:
            dwellers_by_id.update({d.id: d for d in await crud_dweller.get_by_ids(missing_ids, db_session)})
        stepped_up: list[tuple[TeamMember, Dweller]] = []
        for place in promoted:
            dweller = dwellers_by_id.get(place.dweller_id)
            if dweller is not None:
                bio_service.add_entry(dweller, BIO_SOURCE, f"Stepped up to a place on the vault's {TEAM_LABELS[team]}.")
                stepped_up.append((place, dweller))
        return stepped_up

    async def _announce_places(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        team: HazardTeam,
        new_places: list[TeamMember],
        promoted_ids: set[UUID4],
        dwellers_by_id: dict[UUID4, Dweller],
    ) -> None:
        """Tell the owner about every place earned this round, deferred to the round's commit."""
        for place in new_places:
            dweller = dwellers_by_id.get(place.dweller_id)
            if dweller is None:
                continue
            promoted = place.dweller_id in promoted_ids

            async def sender(user_id, place=place, dweller=dweller, promoted=promoted) -> None:
                # A failed flush must roll back to this savepoint (the exception has to
                # leave the block for that) so the round's transaction stays committable.
                async with db_session.begin_nested():
                    await notification_service.notify_hazard_team_joined(
                        db_session,
                        user_id=user_id,
                        vault_id=vault_id,
                        dweller_id=place.dweller_id,
                        dweller_name=dweller.display_name,
                        team=team.value,
                        status=place.status,
                        promoted=promoted,
                        commit=False,
                    )

            await notification_service.notify_owner(
                db_session,
                vault_id,
                context=f"hazard_team_joined vault={vault_id} dweller={place.dweller_id}",
                sender=sender,
            )

    async def equip_hazard_outfits(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        active_gainers: list[Dweller],
        team: HazardTeam,
    ) -> None:
        """Best-effort: give each newly-active member a spare matching outfit.

        Runs AFTER the incident round committed: ``outfit_crud.equip`` commits
        internally, so it must never be called inside the round's transaction.
        Skips dwellers who already wear the target outfit and when no spare is
        available. Never unequips on leaving a team.
        """
        target_name = TEAM_OUTFIT_NAMES[team]
        storage = await crud_storage.get_by_vault(db_session, vault_id)
        if storage is None:
            return
        storage_id = storage.id
        # Read the ids up front: a rollback in the loop expires every loaded instance,
        # so touching dweller/storage attributes afterwards would trigger lazy IO.
        for dweller_id in [dweller.id for dweller in active_gainers]:
            try:
                current = await outfit_crud.get_equipped(db_session, dweller_id)
                if current is not None and current.name == target_name:
                    continue
                spare = await outfit_crud.get_unassigned_in_storage_by_name(db_session, storage_id, target_name)
                if spare is None:
                    continue
                await outfit_crud.equip(db_session=db_session, item_id=spare.id, dweller_id=dweller_id)
            except Exception:  # broad by design: one failed equip must not abort the batch or poison the session
                await db_session.rollback()
                logger.exception("Failed to auto-equip %s on dweller %s", target_name, dweller_id)

    async def dispatch_to_incident(self, db_session: AsyncSession, incident: Incident) -> list[UUID4]:
        """Auto-dispatch the vault's standing hazard team to a matching incident.

        Called right after a hazard incident spawns: active members of the team
        matching the incident's hazard are moved into the incident room and marked
        ``dispatched`` on the incident roster, so the round engine's room-occupancy
        combat picks them up. Best-effort — never raises; returns the ids actually
        moved.
        """
        team = hazard_team_for(incident.type)
        if not team:
            return []
        try:
            active_members = [
                member
                for member in await team_crud.get_hazard_team(db_session, incident.vault_id, team)
                if member.status == ACTIVE_STATUS
            ]
            if not active_members:
                return []

            # Respect the responder cap: only fill the room left on the roster.
            from app.services.combat.incident_service import MAX_INCIDENT_RESPONDERS, committed_responder_ids

            existing = await team_crud.get_incident_team(db_session, incident.id, incident.vault_id)
            room = MAX_INCIDENT_RESPONDERS - len(existing)
            if room <= 0:
                return []

            member_ids = [member.dweller_id for member in active_members]
            dwellers = list(await crud_dweller.get_by_ids_in_vault(db_session, member_ids, incident.vault_id))
            existing_ids = {member.dweller_id for member in existing}
            committed_ids = await committed_responder_ids(
                db_session, incident.vault_id, exclude_incident_id=incident.id
            )
            skipped = [dweller for dweller in dwellers if dweller.id in committed_ids]
            candidates = [
                dweller
                for dweller in dwellers
                if dweller.id not in existing_ids
                and dweller.room_id != incident.room_id
                and dweller.id not in committed_ids
                and is_incident_responder_available(dweller)
            ][:room]
            if not candidates:
                return []

            # Snapshot every responder's posting before the move overwrites room_id,
            # so the return pass can restore their posting.
            origins = {dweller.id: dweller.room_id for dweller in candidates}
            ids = [dweller.id for dweller in candidates]
            members = await team_crud.add_incident_team_members(
                db_session, incident.id, incident.vault_id, ids, status=DISPATCHED_STATUS
            )
            for member in members:
                member.origin_room_id = origins.get(member.dweller_id)
                db_session.add(member)

            from app.services.dweller_service import dweller_service

            dispatched: list[UUID4] = []
            for dweller in candidates:
                try:
                    await dweller_service.update_dweller(db_session, dweller.id, {"room_id": incident.room_id})
                    dispatched.append(dweller.id)
                except Exception:
                    logger.exception("Failed to move dispatched responder %s into incident room", dweller.id)
            if dispatched:
                from app.services.combat import incident_publishing

                incident_publishing.record_event(
                    db_session,
                    incident,
                    "responders_dispatched",
                    f"{len(dispatched)} hazard-team responder(s) dispatched.",
                    data={"skipped": [dweller.first_name for dweller in skipped]} if skipped else None,
                )
                await db_session.commit()
        except Exception:
            logger.exception("Hazard auto-dispatch failed for incident %s", incident.id)
            return []
        else:
            return dispatched

    async def _return_to_posting(self, db_session: AsyncSession, member: TeamMember, incident: Incident) -> bool:
        """Restore a posting with normal capacity checks; wait unassigned if it is busy."""
        from app.services.dweller_service import dweller_service

        dweller = member.dweller
        try:
            origin = await crud_room.get_or_none(db_session, member.origin_room_id) if member.origin_room_id else None
            if origin is not None:
                if dweller.room_id != origin.id:
                    await dweller_service.move_to_room(db_session, member.dweller_id, origin.id)
            # No original posting (or it was demolished): restore unassigned
            # rather than silently selecting a different job.
            elif dweller.room_id == incident.room_id:
                await dweller_service.update_dweller(db_session, member.dweller_id, {"room_id": None})
        except ContentNoChangeException:
            return dweller.room_id is not None
        except ResourceConflictException:
            if dweller.room_id == incident.room_id:
                await dweller_service.update_dweller(db_session, member.dweller_id, {"room_id": None})
            logger.info("Responder %s is waiting for a room to return to", member.dweller_id)
            return False
        return True

    async def return_dispatched_responders(self, db_session: AsyncSession, incident: Incident) -> int:
        """Return manual and automatic responders, retrying full postings on later ticks."""
        try:
            members = await team_crud.get_incident_team(db_session, incident.id, incident.vault_id)
            dispatched = [member for member in members if member.status in COMMITTED_MEMBER_STATUSES]
            if not dispatched:
                return 0

            from app.services.combat.incident_service import committed_responder_ids

            committed = await committed_responder_ids(db_session, incident.vault_id, exclude_incident_id=incident.id)

            returned = 0
            closed = 0
            for member in dispatched:
                dweller = member.dweller
                if dweller is not None and dweller.room_id == incident.room_id and member.dweller_id in committed:
                    # A new incident in the temporary room needs its residents.
                    # Keep the original posting until that defense finishes.
                    continue
                if (
                    dweller is None
                    or dweller.vault_id != incident.vault_id
                    or availability_error(dweller, require_healthy=True) is not None
                    or member.dweller_id in committed
                    or dweller.room_id not in (None, incident.room_id, member.origin_room_id)
                ):
                    # Dead/unavailable responders and newer player assignments must
                    # not be moved. Close the old ledger so it cannot reclaim them.
                    member.status = "completed"
                    db_session.add(member)
                    closed += 1
                    continue
                if not await self._return_to_posting(db_session, member, incident):
                    continue
                member.status = "completed"
                db_session.add(member)
                returned += 1
                closed += 1
            if closed:
                await db_session.commit()
        except Exception:
            logger.exception("Failed to return dispatched responders for incident %s", incident.id)
            return 0
        else:
            return returned

    async def get_roster(self, db_session: AsyncSession, vault_id: UUID4) -> ContaminationTeamRead:
        """Every team's roster for a vault, active places and bench included.

        Service counts come from one grouped participation query per hazard, never
        a per-member read; gear reflects the equipment currently worn.
        """
        teams: list[HazardTeamRosterRead] = []
        for team in HazardTeam:
            places = await team_crud.get_hazard_team(db_session, vault_id, team)
            counts = await incident_participant_crud.count_incidents_by_dweller(
                db_session, [place.dweller_id for place in places], HAZARD_TEAM_INCIDENT_TYPES[team]
            )
            active = [
                _place_read(place, team, counts.get(place.dweller_id, 0))
                for place in places
                if place.status == ACTIVE_STATUS
            ]
            reserve = [
                _place_read(place, team, counts.get(place.dweller_id, 0))
                for place in places
                if place.status == RESERVE_STATUS
            ]
            teams.append(HazardTeamRosterRead(team=team, active=active, reserve=reserve))
        return ContaminationTeamRead(vault_id=vault_id, teams=teams)

    async def set_place(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        team: HazardTeam,
        dweller_id: UUID4,
        *,
        active: bool,
    ) -> ContaminationTeamRead:
        """Manually move a team member between Active and Reserve.

        Activating is idempotent when the member is already active and refuses to
        exceed ``TEAM_SIZE``; benching is idempotent when already on the bench and
        leaves the slot open — a voluntary stand-down never unequips and never
        auto-promotes a reserve member.
        """
        if not await db_locks.try_advisory_xact_lock(db_session, roster_lock_key(vault_id, team)):
            raise ResourceConflictException("Team roster is busy — try again")
        member = await team_crud.get_hazard_member(db_session, vault_id, team, dweller_id)
        if member is None:
            raise ResourceNotFoundException(TeamMember, identifier=dweller_id)
        if active:
            if member.status == ACTIVE_STATUS:
                return await self.get_roster(db_session, vault_id)
            if not await self._has_response_station(db_session, vault_id):
                raise ValidationException(
                    detail="A Response Station is required before a dweller can be promoted into a fire or radiation team."
                )
            if not await self._has_response_capacity(db_session, vault_id):
                raise ResourceConflictException(
                    "The Response Station is at capacity — expand it or bench another responder."
                )
            if await team_crud.count_active_hazard(db_session, vault_id, team) >= TEAM_SIZE:
                raise ResourceConflictException("The team already has 3 active members — bench one first.")
            member.status = ACTIVE_STATUS
            member.slot_number = await self._next_free_slot(db_session, vault_id, team)
            db_session.add(member)
            await db_session.commit()
            dweller = await crud_dweller.get_or_none(db_session, member.dweller_id)
            if dweller is not None:
                try:
                    await self.equip_hazard_outfits(db_session, vault_id, [dweller], team)
                except Exception:
                    logger.exception("Failed to auto-equip %s on dweller %s", TEAM_OUTFIT_NAMES[team], dweller.id)
                await bio_service.append_entry(
                    db_session,
                    member.dweller_id,
                    BIO_SOURCE,
                    f"Took an active place on the vault's {TEAM_LABELS[team]}.",
                    {"team": team.value, "status": ACTIVE_STATUS},
                )
        else:
            if member.status == RESERVE_STATUS:
                return await self.get_roster(db_session, vault_id)
            member.status = RESERVE_STATUS
            member.slot_number = None
            db_session.add(member)
            await db_session.commit()
        return await self.get_roster(db_session, vault_id)


hazard_team_service = HazardTeamService()


def _outfit_hazard_resist(team: HazardTeam, outfit: Outfit | None) -> float:
    """The equipped outfit's share of THIS team's hazard; 0.0 only when nothing reduces it."""
    return outfit_radiation_resist(outfit) if team == HazardTeam.RADIATION else outfit_fire_resist(outfit)


def _place_read(place: TeamMember, team: HazardTeam, service_count: int) -> HazardTeamMemberRead:
    outfit = place.dweller.outfit
    return HazardTeamMemberRead(
        dweller_id=place.dweller_id,
        status=place.status,
        name=place.dweller.display_name,
        level=place.dweller.level,
        service_count=service_count,
        outfit_name=outfit.name if outfit is not None else None,
        has_matching_gear=outfit is not None and outfit.name == TEAM_OUTFIT_NAMES[team],
        hazard_resist=_outfit_hazard_resist(team, outfit),
    )
