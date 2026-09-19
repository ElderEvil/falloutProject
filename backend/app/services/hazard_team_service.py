"""Earned hazard teams: service turns into a place on a standing team."""

import logging
from dataclasses import dataclass

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import HazardTeam
from app.crud import outfit as outfit_crud
from app.crud.dweller import dweller as crud_dweller
from app.crud.incident_participant import incident_participant_crud
from app.crud.storage import storage as crud_storage
from app.crud.team import team_crud
from app.models.dweller import Dweller
from app.models.incident import HAZARD_TEAM_INCIDENT_TYPES, Incident, hazard_team_for
from app.models.team import ACTIVE_STATUS, RESERVE_STATUS, TeamMember
from app.schemas.contamination_team import ContaminationTeamRead, HazardTeamMemberRead, HazardTeamRosterRead
from app.services.bio_service import bio_service
from app.services.notification_service import notification_service

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
        # Bench members step up first so seniority holds and a freed place is
        # never handed to the newest arrival.
        promoted = await self._promote_bench(db_session, incident.vault_id, team, dwellers_by_id)
        promoted_ids = {place.dweller_id for place, _ in promoted}
        new_places: list[TeamMember] = [place for place, _ in promoted]
        active_gainers: list[Dweller] = [dweller for _, dweller in promoted]
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
        active_ids = frozenset(
            await team_crud.get_active_hazard_member_ids(db_session, incident.vault_id, team, [d.id for d in dwellers])
        )
        return HazardTeamRoundResult(new_places=new_places, active_gainers=active_gainers, active_ids=active_ids)

    async def _join_if_qualified(
        self, db_session: AsyncSession, vault_id: UUID4, dweller: Dweller, team: HazardTeam
    ) -> TeamMember | None:
        if await team_crud.get_hazard_member(db_session, vault_id, team, dweller.id):
            return None
        fought = await incident_participant_crud.count_incidents(
            db_session, dweller.id, HAZARD_TEAM_INCIDENT_TYPES[team]
        )
        if fought < QUALIFYING_INCIDENTS:
            return None
        active = await team_crud.count_active_hazard(db_session, vault_id, team)
        status = ACTIVE_STATUS if active < TEAM_SIZE else RESERVE_STATUS
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

    async def get_roster(self, db_session: AsyncSession, vault_id: UUID4) -> ContaminationTeamRead:
        """Every team's roster for a vault, active places and bench included."""
        teams: list[HazardTeamRosterRead] = []
        for team in HazardTeam:
            places = await team_crud.get_hazard_team(db_session, vault_id, team)
            teams.append(
                HazardTeamRosterRead(
                    team=team,
                    active=[_place_read(place) for place in places if place.status == ACTIVE_STATUS],
                    reserve=[_place_read(place) for place in places if place.status == RESERVE_STATUS],
                )
            )
        return ContaminationTeamRead(vault_id=vault_id, teams=teams)


hazard_team_service = HazardTeamService()


def _place_read(place: TeamMember) -> HazardTeamMemberRead:
    return HazardTeamMemberRead(dweller_id=place.dweller_id, status=place.status)
