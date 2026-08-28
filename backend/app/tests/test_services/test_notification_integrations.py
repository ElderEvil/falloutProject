"""Tests for notification integrations in game services."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.exploration import ExplorationStatus
from app.models.incident import IncidentStatus, IncidentType
from app.models.notification import NotificationType
from app.services.exploration.coordinator import ExplorationCoordinator
from app.services.incident_service import IncidentService
from app.services.notification_service import NotificationService
from app.services.radio_service import RadioService


class TestExplorationNotifications:
    """Test exploration completion notifications."""

    @pytest.mark.asyncio
    async def test_exploration_complete_sends_notification(
        self,
        async_session: AsyncSession,
        user_with_vault: tuple,
        dweller_in_vault,
    ):
        """Test that completing an exploration sends a notification."""
        user, vault = user_with_vault

        # Create completed exploration
        # Create exploration using proper method that captures dweller stats
        exploration = await crud.exploration.create_with_dweller_stats(
            db_session=async_session,
            vault_id=vault.id,
            dweller_id=dweller_in_vault.id,
            duration=1,
            stimpaks=0,
            radaways=0,
        )

        # Mark as completed (simulate time passing)
        from datetime import UTC, datetime, timedelta

        exploration.start_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)
        exploration.status = ExplorationStatus.ACTIVE
        async_session.add(exploration)
        await async_session.commit()
        await async_session.refresh(exploration)

        coordinator = ExplorationCoordinator()

        # Mock notification service
        with patch(
            "app.services.exploration.coordinator.notification_service.notify_exploration_complete"
        ) as mock_notify:
            mock_notify.return_value = AsyncMock()

            # Complete exploration
            await coordinator.complete_exploration(async_session, exploration.id)

            # Verify notification was called
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args

            assert call_args.kwargs["user_id"] == user.id
            assert call_args.kwargs["vault_id"] == vault.id
            assert call_args.kwargs["dweller_id"] == dweller_in_vault.id
            assert "meta_data" in call_args.kwargs
            assert "caps_earned" in call_args.kwargs["meta_data"]
            assert "xp_earned" in call_args.kwargs["meta_data"]
            assert "items_found" in call_args.kwargs["meta_data"]
            assert call_args.kwargs["meta_data"]["exploration_id"] == str(exploration.id)


class TestRadioNotifications:
    """Test radio recruitment notifications."""

    @pytest.mark.asyncio
    async def test_recruit_dweller_sends_notification(self, async_session: AsyncSession, user_with_vault: tuple):
        """Test that recruiting a dweller sends a notification."""
        user, vault = user_with_vault

        with patch("app.services.radio_service.notification_service.notify_radio_new_dweller") as mock_notify:
            mock_notify.return_value = AsyncMock()

            # Recruit a dweller
            dweller, _ = await RadioService.recruit_dweller(async_session, vault.id)

            # Verify notification was called
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args

            assert call_args.kwargs["user_id"] == user.id
            assert call_args.kwargs["vault_id"] == vault.id
            assert dweller.first_name in call_args.kwargs["dweller_name"]
            assert "meta_data" in call_args.kwargs
            assert "dweller_id" in call_args.kwargs["meta_data"]


class TestIncidentNotifications:
    """Test incident spawn notifications."""

    @pytest.mark.asyncio
    async def test_spawn_incident_sends_notification(
        self,
        async_session: AsyncSession,
        user_with_vault: tuple,
        dweller_in_vault,
        room_in_vault,
    ):
        """Test that spawning an incident sends a notification."""
        user, vault = user_with_vault

        # Assign dweller to room so incident can spawn
        dweller_in_vault.room_id = room_in_vault.id
        async_session.add(dweller_in_vault)
        await async_session.commit()

        incident_service = IncidentService()

        with patch("app.services.incident_service.notification_service.create_and_send") as mock_notify:
            mock_notify.return_value = AsyncMock()

            # Spawn incident
            await incident_service.spawn_incident(async_session, vault.id, IncidentType.FIRE)

            # Verify notification was called
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args

            assert call_args.kwargs["user_id"] == user.id
            assert call_args.kwargs["vault_id"] == vault.id
            assert "Incident" in call_args.kwargs["title"]
            assert "Fire" in call_args.kwargs["title"]
            assert "meta_data" in call_args.kwargs
            assert "incident_id" in call_args.kwargs["meta_data"]
            assert "room_id" in call_args.kwargs["meta_data"]
            assert "incident_type" in call_args.kwargs["meta_data"]
            assert "difficulty" in call_args.kwargs["meta_data"]

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
            with patch("app.services.incident_service.notification_service.create_and_send") as mock_notify:
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

        with patch("app.services.incident_service.notification_service.create_and_send") as mock_notify:
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

        with patch("app.services.incident_service.notification_service.create_and_send") as mock_notify:
            mock_notify.return_value = AsyncMock()

            await incident_service.process_incident(async_session, incident, 60)

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        assert call_args.kwargs["notification_type"] == NotificationType.COMBAT_DEFEAT
        assert call_args.kwargs["vault_id"] == vault.id

    @pytest.mark.asyncio
    async def test_incident_victory_no_notification_when_commit_fails(
        self,
        async_session: AsyncSession,
        user_with_vault: tuple,
        dweller_in_vault,
        room_in_vault,
    ):
        """A resolution notification is not sent if the incident commit fails."""
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
        incident.enemies_defeated = 10
        async_session.add(incident)
        await async_session.commit()
        await async_session.refresh(incident)

        async def fail_commit():  # type: ignore[no-untyped-def]
            raise RuntimeError("commit failed")

        async_session.commit = fail_commit  # type: ignore[method-assign]

        incident_service = IncidentService()

        with (
            patch("app.services.incident_service.notification_service.create_and_send") as mock_notify,
            pytest.raises(RuntimeError),
        ):
            await incident_service.process_incident(async_session, incident, 60)

        mock_notify.assert_not_called()


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
