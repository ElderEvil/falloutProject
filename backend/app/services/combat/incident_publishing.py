"""Incident event reporting: lifecycle journal, SSE pushes, and owner notifications."""

import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.incident import Incident, IncidentType, get_incident_definition
from app.models.incident_event import IncidentEvent
from app.models.notification import NotificationPriority, NotificationType
from app.schemas.incident_sse import IncidentSseEvent
from app.services.notification_service import notification_service
from app.services.stream_manager import sse_manager

logger = logging.getLogger(__name__)

INCIDENT_NAMES: dict[IncidentType, str] = {
    IncidentType.FIRE: "🔥 Fire",
    IncidentType.RADROACH_INFESTATION: "🪳 Radroach Infestation",
    IncidentType.RAIDER_ATTACK: "💀 Raider Attack",
    IncidentType.DEATHCLAW_ATTACK: "👹 Deathclaw Attack",
    IncidentType.MOLE_RAT_ATTACK: "🐀 Mole Rat Attack",
    IncidentType.FERAL_GHOUL_ATTACK: "🧟 Feral Ghoul Attack",
    IncidentType.RADSCORPION_ATTACK: "🦂 Radscorpion Attack",
}


def record_event(
    db_session: AsyncSession, incident: Incident, kind: str, message: str, data: dict | None = None
) -> None:
    """Append a meaningful lifecycle event; callers commit with their state change."""
    db_session.add(IncidentEvent(incident_id=incident.id, kind=kind, message=message, data=data))


async def publish_sse(
    incident: Incident,
    event_type: str,
    *,
    success: bool | None = None,
    caps_earned: int | None = None,
    room_name: str | None = None,
) -> None:
    """Publish a non-critical incident event."""
    try:
        await sse_manager.publish(
            incident.vault_id,
            "incidents",
            IncidentSseEvent(
                event_id=str(incident.id),
                type=event_type,
                incident_id=str(incident.id),
                vault_id=str(incident.vault_id),
                incident_type=incident.type,
                status=incident.status,
                room_id=str(incident.room_id) if incident.room_id else None,
                room_name=room_name,
                difficulty=incident.difficulty,
                success=success,
                caps_earned=caps_earned,
            ).model_dump(),
        )
    except Exception:
        logger.exception(
            "Failed to publish SSE %s: incident_id=%s, vault_id=%s",
            event_type,
            incident.id,
            incident.vault_id,
        )


async def notify_spawn(db_session, incident: Incident, room_name: str, incident_name: str, difficulty: int) -> None:
    """Best-effort: tell the owner a new incident needs a response."""
    await notification_service.notify_owner(
        db_session,
        incident.vault_id,
        context=f"combat_started incident={incident.id} vault={incident.vault_id}",
        sender=lambda user_id: notification_service.create_and_send(
            db_session,
            user_id=user_id,
            vault_id=incident.vault_id,
            notification_type=NotificationType.COMBAT_STARTED,
            priority=NotificationPriority.HIGH,
            title=f"Incident: {incident_name}",
            message=f"{incident_name} in {room_name}! Send dwellers to defend.",
            meta_data={
                "incident_id": str(incident.id),
                "room_id": str(incident.room_id),
                "room_name": room_name,
                "incident_type": incident.type.value,
                "difficulty": difficulty,
            },
        ),
    )


async def notify_resolution(
    db_session: AsyncSession, incident: Incident, *, success: bool, caps_earned: int = 0
) -> None:
    """Best-effort: notify the owner that an incident was resolved."""
    incident_name = INCIDENT_NAMES.get(incident.type, str(incident.type))
    definition = get_incident_definition(incident.type)
    if success:
        if definition.objective.value == "contain":
            title = f"Contained: {incident_name}"
            message = f"Your dwellers contained {incident_name} and recovered {caps_earned} caps!"
        else:
            title = f"Victory: {incident_name}"
            message = f"Your dwellers defeated the attackers and recovered {caps_earned} caps!"
        notification_type = NotificationType.COMBAT_VICTORY
    else:
        title = f"Incident Lost: {incident_name}"
        message = f"Your dwellers failed to contain the {incident_name}."
        notification_type = NotificationType.COMBAT_DEFEAT

    await notification_service.notify_owner(
        db_session,
        incident.vault_id,
        context=f"incident_resolved incident={incident.id} vault={incident.vault_id} success={success}",
        sender=lambda user_id: notification_service.create_and_send(
            db_session,
            user_id=user_id,
            vault_id=incident.vault_id,
            notification_type=notification_type,
            priority=NotificationPriority.HIGH,
            title=title,
            message=message,
            meta_data={
                "incident_id": str(incident.id),
                "incident_type": incident.type.value,
                "loot": incident.loot,
                "caps_earned": caps_earned,
            },
        ),
    )
