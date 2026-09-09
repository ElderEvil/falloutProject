"""Tests for notification integrations in game services."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.exploration import ExplorationStatus
from app.models.incident import IncidentStatus, IncidentType
from app.models.notification import NotificationType
from app.services.combat.incident_service import IncidentService
from app.services.exploration.coordinator import ExplorationCoordinator
from app.services.exploration_service import exploration_service
from app.services.notification_service import NotificationService
from app.services.radio_service import RadioService


class TestIncidentNotifications:
    """Test incident spawn notifications."""

    @pytest.mark.asyncio
    async def test_incident_notification_includes_correct_type(
        self,
        async_session: AsyncSession,
        user_with_vault: tuple,
        dweller_in_vault,
        room_in_vault,
    ):
        """Test that different incident types have correct names in notifications."""
        _, vault = user_with_vault

        dweller_in_vault.room_id = room_in_vault.id
        async_session.add(dweller_in_vault)
        await async_session.commit()

        incident_service = IncidentService()

        incident_types = [
            (IncidentType.FIRE, "Fire"),
            (IncidentType.RADROACH_INFESTATION, "Radroach Infestation"),
            (IncidentType.RAIDER_ATTACK, "Raider Attack"),
        ]

        for incident_type, expected_name in incident_types:
            with patch("app.services.combat.incident_publishing.notification_service.create_and_send") as mock_notify:
                mock_notify.return_value = AsyncMock()

                incident = await incident_service.spawn_incident(async_session, vault.id, incident_type)

                if incident:  # Some might not spawn due to rules
                    call_args = mock_notify.call_args
                    assert expected_name in call_args.kwargs["title"]
                    assert expected_name in call_args.kwargs["message"]

                    # Clean up for next test
                    incident.status = IncidentStatus.RESOLVED
                    async_session.add(incident)
                    await async_session.commit()

    @pytest.mark.asyncio
    async def test_incident_victory_sends_notification(
        self,
        async_session: AsyncSession,
        user_with_vault: tuple,
        dweller_in_vault,
        room_in_vault,
    ):
        """Resolving an incident successfully fires a COMBAT_VICTORY notification."""
        _, vault = user_with_vault

        dweller_in_vault.room_id = room_in_vault.id
        async_session.add(dweller_in_vault)
        await async_session.commit()

        incident = await crud.incident_crud.create(
            async_session,
            vault_id=vault.id,
            room_id=room_in_vault.id,
            incident_type=IncidentType.RADROACH_INFESTATION,
            difficulty=1,
        )
        incident.enemies_defeated = 10  # force immediate victory
        async_session.add(incident)
        await async_session.commit()
        await async_session.refresh(incident)

        incident_service = IncidentService()

        with patch("app.services.combat.incident_publishing.notification_service.create_and_send") as mock_notify:
            mock_notify.return_value = AsyncMock()

            await incident_service.process_incident(async_session, incident, 60)

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        assert call_args.kwargs["notification_type"] == NotificationType.COMBAT_VICTORY
        assert call_args.kwargs["vault_id"] == vault.id
        assert call_args.kwargs["meta_data"]["caps_earned"] >= 0
        assert "loot" in call_args.kwargs["meta_data"]

    @pytest.mark.asyncio
    async def test_incident_defeat_sends_notification(
        self,
        async_session: AsyncSession,
        user_with_vault: tuple,
        room_in_vault,
    ):
        """An incident that cannot be contained fires a COMBAT_DEFEAT notification."""
        _, vault = user_with_vault

        incident = await crud.incident_crud.create(
            async_session,
            vault_id=vault.id,
            room_id=room_in_vault.id,
            incident_type=IncidentType.FIRE,
            difficulty=1,
        )
        incident.start_time = datetime.utcnow() - timedelta(seconds=incident.duration)
        async_session.add(incident)
        await async_session.commit()
        await async_session.refresh(incident)

        incident_service = IncidentService()

        with patch("app.services.combat.incident_publishing.notification_service.create_and_send") as mock_notify:
            mock_notify.return_value = AsyncMock()

            await incident_service.process_incident(async_session, incident, 60)

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        assert call_args.kwargs["notification_type"] == NotificationType.COMBAT_DEFEAT
        assert call_args.kwargs["vault_id"] == vault.id


class TestNotificationService:
    """Tests for the notification service helper."""

    @pytest.mark.asyncio
    async def test_notify_owner_survives_lookup_failure(self, async_session: AsyncSession, user_with_vault: tuple):
        """A failed vault-owner lookup does not propagate out of notify_owner."""
        _, vault = user_with_vault

        with patch("app.crud.vault.vault.get", side_effect=RuntimeError("db down")):
            await NotificationService.notify_owner(
                async_session,
                vault.id,
                context="test",
                sender=lambda user_id: None,
            )


class TestDeliveryDeferral:
    """Delivery queue contract for create_and_send(commit=False)."""

    @pytest.mark.asyncio
    async def test_deferred_parks_until_drained(self, async_session: AsyncSession, user_with_vault: tuple):
        """commit=False sends nothing inline; deliver_deferred sends once and empties the queue."""
        user, vault = user_with_vault
        with (
            patch("app.services.notification_service.manager") as mock_ws,
            patch("app.services.notification_service.sse_manager") as mock_sse,
        ):
            await NotificationService.create_and_send(
                async_session,
                user_id=user.id,
                notification_type=NotificationType.COMBAT_VICTORY,
                title="Queued",
                message="delivered later",
                vault_id=vault.id,
                commit=False,
            )
            mock_ws.send_personal_message.assert_not_called()
            mock_sse.publish.assert_not_called()
            assert len(async_session.info["deferred_notification_deliveries"]) == 1

            await NotificationService.deliver_deferred_notifications(async_session)
            assert mock_ws.send_personal_message.call_count == 1
            assert mock_sse.publish.call_count == 1
            assert "deferred_notification_deliveries" not in async_session.info
            await async_session.rollback()

    @pytest.mark.asyncio
    async def test_discard_drops_queued_delivery(self, async_session: AsyncSession, user_with_vault: tuple):
        """A rolled-back transaction's queued payloads are dropped, never sent."""
        user, vault = user_with_vault
        with (
            patch("app.services.notification_service.manager") as mock_ws,
            patch("app.services.notification_service.sse_manager") as mock_sse,
        ):
            await NotificationService.create_and_send(
                async_session,
                user_id=user.id,
                notification_type=NotificationType.COMBAT_DEFEAT,
                title="discarded",
                message="never delivered",
                vault_id=vault.id,
                commit=False,
            )
            NotificationService.discard_deferred_notifications(async_session)

            await NotificationService.deliver_deferred_notifications(async_session)
            mock_ws.send_personal_message.assert_not_called()
            mock_sse.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_ws_failure_does_not_block_sse(self, async_session: AsyncSession, user_with_vault: tuple):
        """WS and SSE are independent best-effort channels."""
        user, vault = user_with_vault
        with (
            patch(
                "app.services.notification_service.manager",
                **{"send_personal_message.side_effect": RuntimeError("ws down")},
            ) as mock_ws,
            patch("app.services.notification_service.sse_manager") as mock_sse,
        ):
            await NotificationService.create_and_send(
                async_session,
                user_id=user.id,
                notification_type=NotificationType.COMBAT_VICTORY,
                title="independent",
                message="channels",
                vault_id=vault.id,
            )

        mock_ws.send_personal_message.assert_called_once()
        mock_sse.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_drain_of_empty_queue_is_noop(self, async_session: AsyncSession):
        """deliver_deferred on a session with no pendings does nothing."""
        with (
            patch("app.services.notification_service.manager") as mock_ws,
            patch("app.services.notification_service.sse_manager") as mock_sse,
        ):
            await NotificationService.deliver_deferred_notifications(async_session)
        mock_ws.send_personal_message.assert_not_called()
        mock_sse.publish.assert_not_called()
