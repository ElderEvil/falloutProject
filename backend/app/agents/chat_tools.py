"""Tool implementations and action-suggestion policy for the dweller chat agent."""

import logging

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.agents.chat_schemas import (
    DwellerActivityBriefing,
    DwellerChatDeps,
    DwellerChatOutput,
    RoomInfo,
    TrainingOption,
)
from app.core.enums import DwellerStatusEnum, RoomTypeEnum, SPECIALEnum
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.relationship import Relationship
from app.models.room import Room
from app.schemas.chat import (
    AssignToRoomAction,
    NoAction,
    RecallExplorationAction,
    RequestRadawayAction,
    RequestStimpakAction,
    StartExplorationAction,
    StartTrainingAction,
)
from app.schemas.dweller import DwellerReadFull
from app.services.medical_service import (
    get_dweller_medical_status as fetch_dweller_medical_status,
)
from app.services.room_assignment_policy import get_highest_special

logger = logging.getLogger(__name__)


async def get_available_rooms(
    db_session: AsyncSession,
    vault_id: UUID4,
    category: RoomTypeEnum | None = None,
) -> list[RoomInfo]:
    query = select(Room).where(Room.vault_id == vault_id)
    if category is not None:
        query = query.where(Room.category == category)
    response = await db_session.execute(query)
    rooms = response.scalars().all()

    result = []
    for room in rooms:
        dweller_query = select(Dweller).where(Dweller.room_id == room.id).where(~Dweller.is_deleted)
        dweller_response = await db_session.execute(dweller_query)
        current_dwellers = len(dweller_response.scalars().all())

        max_capacity = (room.size or room.size_min) // 3 * 2 if room.size or room.size_min else 2

        if current_dwellers < max_capacity:
            result.append(
                RoomInfo(
                    room_id=str(room.id),
                    name=room.name,
                    category=room.category.value,
                    current_dwellers=current_dwellers,
                    max_capacity=max_capacity,
                    ability=room.ability.value if room.ability else None,
                )
            )

    return result


async def build_dweller_activity_briefing(deps: DwellerChatDeps) -> DwellerActivityBriefing:
    """Read the activity state that determines safe chat-action suggestions."""
    from app.crud import exploration as exploration_crud
    from app.crud import training as training_crud
    from app.services.medical_service import get_available_medical_supplies
    from app.services.training_service import training_service

    active_training = await training_crud.training.get_active_by_dweller(deps.db_session, deps.dweller.id)
    active_exploration = await exploration_crud.get_by_dweller(deps.db_session, dweller_id=deps.dweller.id)
    available_stimpaks, available_radaways = await get_available_medical_supplies(
        deps.db_session, deps.dweller, deps.vault_id
    )

    briefing = DwellerActivityBriefing(
        active_training_stat=active_training.stat_being_trained if active_training else None,
        active_training_progress_percent=round(active_training.progress_percentage(), 1) if active_training else None,
        exploration_active=active_exploration is not None,
        exploration_progress_percent=round(active_exploration.progress_percentage(), 1) if active_exploration else None,
        exploration_duration_hours=active_exploration.duration if active_exploration else None,
        available_stimpaks=available_stimpaks,
        available_radaways=available_radaways,
    )

    if active_training:
        briefing.training_blocker = f"Already training {active_training.stat_being_trained.value}."
    else:
        rooms_result = await deps.db_session.execute(
            select(Room).where(Room.vault_id == deps.vault_id).where(Room.category == RoomTypeEnum.TRAINING)
        )
        rooms = rooms_result.scalars().all()
        active_trainings = await training_crud.training.get_active_by_vault(deps.db_session, deps.vault_id)
        active_by_room: dict[UUID4, int] = {}
        for training in active_trainings:
            active_by_room[training.room_id] = active_by_room.get(training.room_id, 0) + 1

        for room in rooms:
            if room.ability is None:
                continue
            current_stat = getattr(deps.dweller, room.ability.value)
            if current_stat >= game_config.training.special_stat_max:
                continue
            capacity = room.capacity or max((room.size or room.size_min or 3) // 3 * 2, 1)
            capacity_remaining = capacity - active_by_room.get(room.id, 0)
            if capacity_remaining <= 0:
                continue
            briefing.training_options.append(
                TrainingOption(
                    room_name=room.name,
                    stat=room.ability,
                    current_stat=current_stat,
                    capacity_remaining=capacity_remaining,
                    estimated_duration_hours=round(
                        training_service.calculate_training_duration(current_stat, room.tier) / 3600,
                        1,
                    ),
                )
            )
        if not briefing.training_options:
            briefing.training_blocker = "No available training room can improve this dweller right now."

    if active_exploration:
        briefing.exploration_blocker = "Already exploring; suggest recall instead of another expedition."
    else:
        briefing.recommended_exploration_duration_hours = 4
        briefing.recommended_stimpaks = min(2, available_stimpaks)
        briefing.recommended_radaways = min(1, available_radaways)

    return briefing


async def build_dweller_social_context(deps: DwellerChatDeps) -> dict:
    """Return the current social status, family, and relationship state for chat answers."""
    dweller = await deps.db_session.get(Dweller, deps.dweller.id)
    if dweller is None:
        return {"status": "Unknown", "room_name": None, "family": [], "relationships": []}

    room_name = None
    if dweller.room_id:
        room_result = await deps.db_session.execute(select(Room.name).where(Room.id == dweller.room_id))
        room_name = room_result.scalar_one_or_none()

    relationships_result = await deps.db_session.execute(
        select(Relationship).where(
            (Relationship.dweller_1_id == dweller.id) | (Relationship.dweller_2_id == dweller.id)
        )
    )
    relationships = relationships_result.scalars().all()
    relation_ids = {
        relation.dweller_2_id if relation.dweller_1_id == dweller.id else relation.dweller_1_id
        for relation in relationships
    }
    family_ids = {
        member_id for member_id in (dweller.partner_id, dweller.parent_1_id, dweller.parent_2_id) if member_id
    }
    relatives_result = await deps.db_session.execute(
        select(Dweller).where(
            Dweller.id.in_(family_ids | relation_ids)
            | (Dweller.parent_1_id == dweller.id)
            | (Dweller.parent_2_id == dweller.id)
        )
    )
    relatives = {relative.id: relative for relative in relatives_result.scalars().all()}

    def name(member_id: UUID4) -> str:
        member = relatives.get(member_id)
        return f"{member.first_name} {member.last_name or ''}".strip() if member else "Unknown dweller"

    family = [
        {"name": name(member_id), "relation": relation}
        for member_id, relation in (
            (dweller.partner_id, "partner"),
            (dweller.parent_1_id, "parent"),
            (dweller.parent_2_id, "parent"),
        )
        if member_id
    ]
    family.extend(
        {"name": name(child.id), "relation": "child"}
        for child in relatives.values()
        if child.parent_1_id == dweller.id or child.parent_2_id == dweller.id
    )
    return {
        "status": "Socializing" if dweller.status == DwellerStatusEnum.RESTING else dweller.status.value.title(),
        "room_name": room_name,
        "family": family,
        "relationships": [
            {
                "name": name(relation.dweller_2_id if relation.dweller_1_id == dweller.id else relation.dweller_1_id),
                "relationship_type": relation.relationship_type.value,
                "affinity": relation.affinity,
            }
            for relation in relationships
        ],
    }


def best_room_recommendation_text(dweller: DwellerReadFull) -> str:
    """Recommend a room based on the dweller's highest SPECIAL stat."""
    best_stat = get_highest_special(dweller)
    best_value = getattr(dweller, best_stat.value)

    stat_room_map = {
        SPECIALEnum.STRENGTH: "Power Generator",
        SPECIALEnum.PERCEPTION: "Water Treatment",
        SPECIALEnum.ENDURANCE: "Nuka-Cola Bottler",
        SPECIALEnum.CHARISMA: "Radio Studio",
        SPECIALEnum.INTELLIGENCE: "Medbay/Science Lab",
        SPECIALEnum.AGILITY: "Diner",
        SPECIALEnum.LUCK: "Game Room",
    }

    default_room = "any production room"
    recommended_room = stat_room_map.get(best_stat, default_room)

    return (
        f"Dweller's best stat is {best_stat.value} ({best_value}). "
        f"Recommended room type: {recommended_room}. "
        f"Look for production rooms with ability={best_stat.value} in the available rooms list."
    )


async def parse_action_suggestion(
    output: DwellerChatOutput,
    db_session: AsyncSession,
    dweller: DwellerReadFull,
) -> (
    AssignToRoomAction
    | StartTrainingAction
    | StartExplorationAction
    | RecallExplorationAction
    | RequestStimpakAction
    | RequestRadawayAction
    | NoAction
):
    """Convert agent output to action suggestion schema with deterministic enrichment.

    Policy enforcement:
    - Training actions are only suggested for non-neutral sentiment (sentiment_score != 0)
    - Neutral messages should not suggest training, even if agent suggests it
    - Medical needs take priority over every other action while supplies are available
    - Activity actions are re-checked against current server state before an action card is emitted
    """

    medical_status = await fetch_dweller_medical_status(db_session, dweller, dweller.vault_id)
    if medical_status.recommended_action == "request_stimpak":
        reason = output.action_reason if output.action_type == "request_stimpak" else None
        return RequestStimpakAction(reason=reason or "Health is below 50%")
    if medical_status.recommended_action == "request_radaway":
        reason = output.action_reason if output.action_type == "request_radaway" else None
        return RequestRadawayAction(reason=reason or "Radiation is at least 30% of maximum health")

    if output.action_type == "no_action":
        return NoAction(reason=output.action_reason)
    if output.action_type == "assign_to_room" and output.action_room_id and output.action_room_name:
        return AssignToRoomAction(
            room_id=output.action_room_id,
            room_name=output.action_room_name,
            reason=output.action_reason or "Based on conversation context",
        )
    if output.action_type == "start_training" and output.action_stat:
        # Policy: Filter out training actions for neutral sentiment
        if output.sentiment_score == 0:
            return NoAction(reason="Training not suggested for neutral messages")
        briefing = await build_dweller_activity_briefing(
            DwellerChatDeps(db_session=db_session, dweller=dweller, vault_id=dweller.vault_id)
        )
        if briefing.active_training_stat:
            return NoAction(reason=briefing.training_blocker)
        if not any(option.stat == output.action_stat for option in briefing.training_options):
            return NoAction(reason=briefing.training_blocker or "No room is available for that training right now.")
        return StartTrainingAction(
            stat=output.action_stat,
            reason=output.action_reason or "Based on conversation context",
        )
    if output.action_type == "start_exploration":
        briefing = await build_dweller_activity_briefing(
            DwellerChatDeps(db_session=db_session, dweller=dweller, vault_id=dweller.vault_id)
        )
        if briefing.exploration_active:
            return NoAction(reason=briefing.exploration_blocker)
        # Use current vault + dweller supplies. The exploration service re-checks these values at mutation time.
        duration = min(max(1, output.action_duration_hours or briefing.recommended_exploration_duration_hours or 4), 24)
        stimpaks = min(
            briefing.available_stimpaks,
            max(
                0, output.action_stimpaks if output.action_stimpaks is not None else briefing.recommended_stimpaks or 0
            ),
        )
        radaways = min(
            briefing.available_radaways,
            max(
                0, output.action_radaways if output.action_radaways is not None else briefing.recommended_radaways or 0
            ),
        )
        return StartExplorationAction(
            duration_hours=duration,
            stimpaks=stimpaks,
            radaways=radaways,
            reason=output.action_reason or "Ready for wasteland exploration",
        )
    if output.action_type == "recall_exploration":
        briefing = await build_dweller_activity_briefing(
            DwellerChatDeps(db_session=db_session, dweller=dweller, vault_id=dweller.vault_id)
        )
        if not briefing.exploration_active:
            return NoAction(reason="Dweller is not currently exploring the wasteland")
        # Deterministic enrichment: re-query immediately before emitting the actionable exploration ID.
        from app.crud.exploration import exploration as exploration_crud

        active_exploration = await exploration_crud.get_by_dweller(db_session, dweller_id=dweller.id)
        if active_exploration:
            return RecallExplorationAction(
                exploration_id=active_exploration.id,
                reason=output.action_reason or "Recall dweller from wasteland",
            )
        # No active exploration found - return NoAction
        return NoAction(reason="Dweller is not currently exploring the wasteland")
    if output.action_type in {"request_stimpak", "request_radaway"}:
        if output.action_type == "request_stimpak":
            if medical_status.health_percent >= 50:
                return NoAction(reason="Dweller does not currently need a Stimpak")
            if medical_status.available_stimpaks <= 0:
                return NoAction(reason="No Stimpaks are available")
            return RequestStimpakAction(reason=output.action_reason or "Health is below 50%")
        if medical_status.radiation_percent < 30:
            return NoAction(reason="Dweller does not currently need RadAway")
        if medical_status.available_radaways <= 0:
            return NoAction(reason="No RadAway is available")
        return RequestRadawayAction(reason=output.action_reason or "Radiation is at least 30%")
    return NoAction(reason=output.action_reason)


def derive_reason_code(sentiment_score: int) -> str:
    """Derive reason code from sentiment score."""
    if sentiment_score > 0:
        return "chat_positive"
    if sentiment_score < 0:
        return "chat_negative"
    return "chat_neutral"


def compute_happiness_delta(sentiment_score: int) -> int:
    """Convert sentiment score (-5 to +5) to happiness delta (-10 to +10).

    Uses the sentiment_delta_mapping from HappinessConfig to look up the delta value.
    """
    return game_config.happiness.get_happiness_delta(sentiment_score)
