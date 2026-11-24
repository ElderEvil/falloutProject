from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import IncidentStatus, IncidentType, NotificationType
from app.core.game_config import game_config
from app.models.notification import Notification
from app.services.combat.incident_service import IncidentService
from app.services.notification_service import NotificationService
from app.tests.test_services._transaction_helpers import fail_sql
from app.utils.time import utcnow

PUBLISHING = "app.services.combat.incident_publishing.notification_service.create_and_send"
HTTP_METHODS = (
    "app.services.notification_service.manager.send_personal_message",
    "app.services.notification_service.sse_manager.publish",
)


@pytest.fixture
def send_mocks():
    with (
        patch(HTTP_METHODS[0], new_callable=AsyncMock) as ws,
        patch(HTTP_METHODS[1], new_callable=AsyncMock) as sse,
    ):
        yield ws, sse


@pytest.fixture
def channel_mocks():
    with (
        patch("app.services.notification_service.manager") as ws,
        patch("app.services.notification_service.sse_manager") as sse,
    ):
        yield ws, sse


@pytest.fixture
async def staffed_room(async_session: AsyncSession, dweller_in_vault, room_in_vault):
    dweller_in_vault.room_id = room_in_vault.id
    async_session.add(dweller_in_vault)
    await async_session.commit()
    return room_in_vault


async def _send(session, user, vault, *, ntype=NotificationType.COMBAT_VICTORY, title, message, commit=True):
    return await NotificationService.create_and_send(
        session,
        user_id=user.id,
        notification_type=ntype,
        title=title,
        message=message,
        vault_id=vault.id,
        commit=commit,
    )


async def _incident(session, vault, room, incident_type, **fields):
    incident = await crud.incident_crud.create(
        session, vault_id=vault.id, room_id=room.id, incident_type=incident_type, difficulty=1
    )
    for name, value in fields.items():
        setattr(incident, name, value)
    session.add(incident)
    await session.commit()
    await session.refresh(incident)
    return incident


async def test_earned_objective_explains_claim_availability(async_session, user_with_vault, send_mocks):
    user, vault = user_with_vault
    ready = await NotificationService.notify_objective_completed(
        async_session, user.id, vault.id, "Scrap a rare weapon", "300 caps", meta_data={"ready_to_claim": True}
    )
    pending = await NotificationService.notify_objective_completed(
        async_session, user.id, vault.id, "Scrap a rare weapon", "300 caps", meta_data={"ready_to_claim": False}
    )
    assert ready.notification_type == NotificationType.OBJECTIVE_COMPLETED
    assert ready.title == "Objective Reward Ready"
    assert "claim 300 caps in Objectives" in ready.message
    assert pending.title == "Objective Complete!"
    assert "completed! Reward: 300 caps" in pending.message


async def test_incident_notification_includes_correct_type(
    async_session: AsyncSession, user_with_vault: tuple, staffed_room
):
    _, vault = user_with_vault
    incident_service = IncidentService()
    for incident_type, expected_name in [
        (IncidentType.FIRE, "Fire"),
        (IncidentType.RADROACH_INFESTATION, "Radroach Infestation"),
        (IncidentType.RAIDER_ATTACK, "Raider Attack"),
    ]:
        with patch(PUBLISHING) as mock_notify:
            mock_notify.return_value = AsyncMock()
            incident = await incident_service.spawn_incident(async_session, vault.id, incident_type)
            if incident:  # Some might not spawn due to rules
                call_args = mock_notify.call_args
                assert expected_name in call_args.kwargs["title"]
                assert expected_name in call_args.kwargs["message"]
                incident.status = IncidentStatus.RESOLVED
                async_session.add(incident)
                await async_session.commit()


async def test_incident_victory_sends_notification(async_session: AsyncSession, user_with_vault: tuple, staffed_room):
    _, vault = user_with_vault
    incident = await _incident(
        async_session, vault, staffed_room, IncidentType.RADROACH_INFESTATION, enemies_defeated=10
    )
    with patch(PUBLISHING) as mock_notify:
        mock_notify.return_value = AsyncMock()
        await IncidentService().process_incident(async_session, incident, 60)
    mock_notify.assert_called_once()
    call_args = mock_notify.call_args
    assert call_args.kwargs["notification_type"] == NotificationType.COMBAT_VICTORY
    assert call_args.kwargs["vault_id"] == vault.id
    assert call_args.kwargs["meta_data"]["caps_earned"] >= 0
    assert "loot" in call_args.kwargs["meta_data"]


async def test_fire_victory_does_not_promise_caps(async_session: AsyncSession, user_with_vault: tuple, staffed_room):
    """A hazard pays in experience, so its notification must not claim caps."""
    _, vault = user_with_vault
    incident = await _incident(async_session, vault, staffed_room, IncidentType.FIRE, combat_progress=1)
    with patch(PUBLISHING) as mock_notify:
        mock_notify.return_value = AsyncMock()
        await IncidentService().process_incident(async_session, incident, 60)
    message = mock_notify.call_args.kwargs["message"]
    assert "caps" not in message
    assert "XP" in message


async def test_incident_defeat_sends_notification(async_session: AsyncSession, user_with_vault: tuple, room_in_vault):
    _, vault = user_with_vault
    incident = await _incident(async_session, vault, room_in_vault, IncidentType.FIRE)
    incident.start_time = utcnow() - timedelta(
        seconds=incident.duration + game_config.incident.response_grace_seconds + 1
    )
    async_session.add(incident)
    await async_session.commit()
    await async_session.refresh(incident)
    with patch(PUBLISHING) as mock_notify:
        mock_notify.return_value = AsyncMock()
        await IncidentService().process_incident(async_session, incident, 60)
    mock_notify.assert_called_once()
    call_args = mock_notify.call_args
    assert call_args.kwargs["notification_type"] == NotificationType.COMBAT_DEFEAT
    assert call_args.kwargs["vault_id"] == vault.id


async def test_notify_owner_survives_lookup_failure(async_session: AsyncSession, user_with_vault: tuple):
    """A failed vault-owner lookup does not propagate out of notify_owner."""
    _, vault = user_with_vault
    with patch("app.crud.vault.vault.get", side_effect=RuntimeError("db down")):
        await NotificationService.notify_owner(async_session, vault.id, context="test", sender=lambda user_id: None)


async def test_deferred_parks_until_drained(async_session: AsyncSession, user_with_vault: tuple, channel_mocks):
    """Delivery queue contract for create_and_send(commit=False)."""
    user, vault = user_with_vault
    mock_ws, mock_sse = channel_mocks
    await _send(async_session, user, vault, title="Queued", message="delivered later", commit=False)
    mock_ws.send_personal_message.assert_not_called()
    mock_sse.publish.assert_not_called()
    assert len(async_session.info["deferred_notification_deliveries"]) == 1
    await NotificationService.deliver_deferred_notifications(async_session)
    assert mock_ws.send_personal_message.call_count == 1
    assert mock_sse.publish.call_count == 1
    assert "deferred_notification_deliveries" not in async_session.info
    await async_session.rollback()


async def test_discard_drops_queued_delivery(async_session: AsyncSession, user_with_vault: tuple, channel_mocks):
    """A rolled-back transaction's queued payloads are dropped, never sent."""
    user, vault = user_with_vault
    mock_ws, mock_sse = channel_mocks
    await _send(
        async_session,
        user,
        vault,
        ntype=NotificationType.COMBAT_DEFEAT,
        title="discarded",
        message="never delivered",
        commit=False,
    )
    NotificationService.discard_deferred_notifications(async_session)
    await NotificationService.deliver_deferred_notifications(async_session)
    mock_ws.send_personal_message.assert_not_called()
    mock_sse.publish.assert_not_called()


async def test_failed_room_unlock_staging_discards_the_parked_recruit(
    async_session: AsyncSession, user_with_vault: tuple, channel_mocks
):
    """A staging failure after the recruit is parked must not leave a payload in ``db.info``
    for a later commit to deliver.
    """
    user, vault = user_with_vault
    mock_ws, mock_sse = channel_mocks
    # A rollback expires loaded instances, so capture the ids the retry query needs.
    user_id, vault_id = user.id, vault.id
    # Make the fixture vault durable: the failure below rolls back only the announcement.
    await async_session.commit()

    with pytest.raises(RuntimeError, match="room-unlock summary staging failed"):
        async with fail_sql(
            async_session,
            lambda statement: "count(" in statement.lower() and "from dweller" in statement.lower(),
            "room-unlock summary staging failed",
        ):
            await NotificationService.notify_radio_new_dweller(async_session, user_id, vault_id, "Rolled Back Recruit")

    mock_ws.send_personal_message.assert_not_called()
    mock_sse.publish.assert_not_called()
    assert "deferred_notification_deliveries" not in async_session.info

    # A retry on the same session must deliver its own notice and nothing else.
    await NotificationService.notify_radio_new_dweller(async_session, user_id, vault_id, "Kept Recruit")

    mock_ws.send_personal_message.assert_called_once()
    payload = mock_ws.send_personal_message.call_args.args[0]
    assert "Kept Recruit" in payload["notification"]["message"]
    assert "Rolled Back Recruit" not in payload["notification"]["message"]
    assert "deferred_notification_deliveries" not in async_session.info

    rows = (await async_session.execute(select(Notification).where(Notification.user_id == user_id))).scalars().all()
    assert len(rows) == 1
    assert "Kept Recruit" in rows[0].message


async def test_ws_failure_does_not_block_sse(async_session: AsyncSession, user_with_vault: tuple, send_mocks):
    user, vault = user_with_vault
    mock_ws, mock_sse = send_mocks
    mock_ws.side_effect = RuntimeError("ws down")
    await _send(async_session, user, vault, title="independent", message="channels")
    mock_ws.assert_called_once()
    mock_sse.assert_called_once()


async def test_drain_of_empty_queue_is_noop(async_session: AsyncSession, channel_mocks):
    mock_ws, mock_sse = channel_mocks
    await NotificationService.deliver_deferred_notifications(async_session)
    mock_ws.send_personal_message.assert_not_called()
    mock_sse.publish.assert_not_called()
