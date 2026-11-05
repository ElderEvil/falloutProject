"""Tests for broadcast service — daily cache, regenerate cap, TTS failure degradation.

All HTTP and S3 are mocked via unittest.mock.
No network in CI.
"""

import sys
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Ensure conftest mocking is active before importing broadcast_service
sys.modules.pop("app.services.storage", None)
sys.modules.pop("app.services.storage.factory", None)


@pytest.fixture(autouse=True)
def _mock_vault_lock():
    """The unit tests use AsyncMock sessions, not a real vault row."""
    with patch(
        "app.services.broadcast_service.crud.vault.get_for_update",
        new=AsyncMock(return_value=MagicMock()),
    ):
        yield


@pytest.fixture(autouse=True)
def _mock_storage():
    """Mock the storage module before any broadcast_service import."""
    mock_mod = MagicMock()
    mock_inst = MagicMock()
    mock_inst.enabled = False
    mock_mod.factory.create_storage_service.return_value = mock_inst
    mock_mod.factory.get_storage_client.return_value = None
    mock_mod.get_storage_client.return_value = None
    # Also patch the factory module's get_storage_client directly
    mock_mod.get_storage_client = MagicMock(return_value=None)
    sys.modules["app.services.storage"] = mock_mod
    sys.modules["app.services.storage.factory"] = mock_mod.factory


class TestDailyCache:
    """Second GET on same day must NOT re-call TTS."""

    @pytest.mark.asyncio
    async def test_second_get_same_day_no_recall(
        self,
    ):
        from app.services import broadcast_service, openrouter_tts_service
        from app.services.broadcast_service import get_or_create_daily

        mock_db = AsyncMock()

        # Patch the TTS service to track calls
        with patch.object(broadcast_service, "get_openrouter_tts_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_enabled = True
            import io
            import wave

            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(44100)
                wf.writeframes(b"\x00" * 100)
            mock_service.generate_speech = AsyncMock(return_value=buf.getvalue())
            mock_get.return_value = mock_service

            # First call: no existing broadcast (CRUD returns None)
            with patch("app.services.broadcast_service.get_today_broadcast", new_callable=AsyncMock) as mock_get_today:
                mock_get_today.return_value = None

                # Patch create_broadcast for the DB commit path
                mock_broadcast = MagicMock()
                mock_broadcast.id = uuid4()
                mock_broadcast.title = "New Title"
                mock_broadcast.script = "New script"
                mock_broadcast.audio_key = None
                mock_broadcast.trigger = "manual"
                mock_broadcast.created_at = datetime.now(UTC)

                with patch("app.services.broadcast_service.create_broadcast", new_callable=AsyncMock) as mock_create:
                    mock_create.return_value = mock_broadcast

                    result = await get_or_create_daily(
                        mock_db,
                        vault_id=uuid4(),
                        vault_data={
                            "number": 1,
                            "population": 10,
                            "population_max": 20,
                            "bottle_caps": 500,
                            "happiness": 70,
                            "power": 50,
                            "power_max": 100,
                            "food": 50,
                            "food_max": 100,
                            "water": 50,
                            "water_max": 100,
                        },
                        recent_notifications=[],
                        gender_counts=[],
                    )

                    # First call should have called TTS
                    mock_service.generate_speech.assert_called_once()
                    assert result["title"] == "New Title"
                    assert result["script"] == "New script"

                    # Reset the TTS mock BEFORE the second call
                    mock_service.generate_speech.reset_mock()

            # Second call: simulate existing broadcast for today
            from app.models.broadcast import Broadcast

            mock_existing = MagicMock()
            mock_existing.id = uuid4()
            mock_existing.title = "Test Title"
            mock_existing.script = "Test script"
            mock_existing.audio_key = "broadcasts/2026/11/05/test.mp3"
            mock_existing.trigger = "daily"
            mock_existing.created_at = datetime.now(UTC)

            with (
                patch("app.services.broadcast_service.get_today_broadcast", new_callable=AsyncMock) as mock_get_today,
                patch("app.services.broadcast_service.get_storage_client", return_value=None),
            ):
                mock_get_today.return_value = mock_existing

                result = await get_or_create_daily(
                    mock_db,
                    vault_id=uuid4(),
                    vault_data={
                        "number": 1,
                        "population": 10,
                        "population_max": 20,
                        "bottle_caps": 500,
                        "happiness": 70,
                        "power": 50,
                        "power_max": 100,
                        "food": 50,
                        "food_max": 100,
                        "water": 50,
                        "water_max": 100,
                    },
                )

                # TTS must NOT be called again
                mock_service.generate_speech.assert_not_called()
                assert result["title"] == "Test Title"
                assert result["script"] == "Test script"
                assert result["audio_url"] is None

    @pytest.mark.asyncio
    async def test_cached_broadcast_returns_public_url(self):
        from app.services.broadcast_service import get_or_create_daily

        mock_db = AsyncMock()
        row = MagicMock()
        row.id = uuid4()
        row.title = "Cached"
        row.script = "Cached script"
        row.audio_key = "broadcasts/2026/11/05/cached.mp3"
        row.trigger = "daily"
        row.created_at = datetime.now(UTC)
        client = MagicMock()
        client.public_url.return_value = "https://cdn.example/broadcasts/2026/11/05/cached.mp3"

        with (
            patch(
                "app.services.broadcast_service.get_today_broadcast",
                new=AsyncMock(return_value=row),
            ),
            patch("app.services.broadcast_service.get_storage_client", return_value=client),
        ):
            result = await get_or_create_daily(mock_db, vault_id=uuid4())

        assert result["audio_url"] == "https://cdn.example/broadcasts/2026/11/05/cached.mp3"

    @pytest.mark.asyncio
    async def test_missing_population_is_read_from_vault(self):
        from app.services.broadcast_service import get_or_create_daily

        mock_db = AsyncMock()
        row = MagicMock()
        row.id = uuid4()
        row.title = "Population"
        row.script = "Population script"
        row.audio_key = None
        row.trigger = "daily"
        row.created_at = datetime.now(UTC)
        tts = MagicMock()
        tts.is_enabled = False

        with (
            patch(
                "app.services.broadcast_service.get_today_broadcast",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.broadcast_service.crud.vault.get_population",
                new=AsyncMock(return_value=7),
            ),
            patch("app.services.broadcast_service.get_openrouter_tts_service", return_value=tts),
            patch(
                "app.services.broadcast_service.create_broadcast",
                new=AsyncMock(return_value=row),
            ) as create,
        ):
            await get_or_create_daily(
                mock_db,
                vault_id=uuid4(),
                vault_data={
                    "number": 1,
                    "population_max": 20,
                    "bottle_caps": 0,
                    "happiness": 50,
                    "power": 0,
                    "power_max": 1,
                    "food": 0,
                    "food_max": 1,
                    "water": 0,
                    "water_max": 1,
                },
                recent_notifications=[],
                gender_counts=[],
            )

        assert "7 brave souls" in create.call_args.kwargs["script"]


class TestRegenerateCap:
    """Rate limit: max 3 manual regenerations per UTC day per vault."""

    @pytest.mark.asyncio
    async def test_regenerate_exceeds_cap(self):
        from app.services.broadcast_service import regenerate

        mock_db = AsyncMock()

        # Patch CRUD to return 3 existing manual regenerations today
        with patch("app.services.broadcast_service.count_trigger_on_date", new_callable=AsyncMock) as mock_count:
            mock_count.return_value = 3

            with pytest.raises(Exception) as exc_info:
                await regenerate(mock_db, vault_id=uuid4())
            assert "limit reached" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_regenerate_under_cap_proceeds(self):
        from app.services import broadcast_service
        from app.services.broadcast_service import regenerate

        mock_db = AsyncMock()

        # Patch count to return 2 (under cap), and get_today_broadcast to return None
        with patch("app.services.broadcast_service.count_trigger_on_date", new_callable=AsyncMock) as mock_count:
            mock_count.return_value = 2

            with patch("app.services.broadcast_service.get_today_broadcast", new_callable=AsyncMock) as mock_get_today:
                mock_get_today.return_value = None

                # Mock create_broadcast for the DB commit path
                mock_broadcast = MagicMock()
                mock_broadcast.id = uuid4()
                mock_broadcast.title = "Regenerated Title"
                mock_broadcast.script = "Regenerated script"
                mock_broadcast.audio_key = None
                mock_broadcast.trigger = "manual"
                mock_broadcast.created_at = datetime.now(UTC)

                with patch("app.services.broadcast_service.create_broadcast", new_callable=AsyncMock) as mock_create:
                    mock_create.return_value = mock_broadcast

                    with patch.object(broadcast_service, "get_openrouter_tts_service") as mock_get:
                        mock_service = MagicMock()
                        mock_service.is_enabled = True
                        import io
                        import wave

                        buf = io.BytesIO()
                        with wave.open(buf, "wb") as wf:
                            wf.setnchannels(1)
                            wf.setsampwidth(2)
                            wf.setframerate(44100)
                            wf.writeframes(b"\x00" * 100)
                        mock_service.generate_speech = AsyncMock(return_value=buf.getvalue())
                        mock_get.return_value = mock_service

                        result = await regenerate(
                            mock_db,
                            vault_id=uuid4(),
                            vault_data={
                                "number": 1,
                                "population": 10,
                                "population_max": 20,
                                "bottle_caps": 500,
                                "happiness": 70,
                                "power": 50,
                                "power_max": 100,
                                "food": 50,
                                "food_max": 100,
                                "water": 50,
                                "water_max": 100,
                            },
                            recent_notifications=[],
                            gender_counts=[],
                        )
                        assert result is not None
                        assert result["trigger"] == "manual"


class TestTTSFailureDegradation:
    """When TTS fails, the endpoint returns script-only (never 500)."""

    @pytest.mark.asyncio
    async def test_tts_failure_returns_script_only(self):
        from app.services import broadcast_service
        from app.services.broadcast_service import get_or_create_daily
        from app.utils.exceptions import TTSProviderException

        mock_db = AsyncMock()

        # No existing broadcast
        with patch("app.services.broadcast_service.get_today_broadcast", new_callable=AsyncMock) as mock_get_today:
            mock_get_today.return_value = None

            # Mock create_broadcast for the DB commit path
            mock_broadcast = MagicMock()
            mock_broadcast.id = uuid4()
            mock_broadcast.title = "Fallback Title"
            mock_broadcast.script = "Fallback script"
            mock_broadcast.audio_key = None
            mock_broadcast.trigger = "daily"
            mock_broadcast.created_at = datetime.now(UTC)

            with patch("app.services.broadcast_service.create_broadcast", new_callable=AsyncMock) as mock_create:
                mock_create.return_value = mock_broadcast

                with patch.object(broadcast_service, "get_openrouter_tts_service") as mock_get:
                    mock_service = MagicMock()
                    mock_service.is_enabled = True
                    mock_service.generate_speech = AsyncMock(side_effect=TTSProviderException("OpenRouter unreachable"))
                    mock_get.return_value = mock_service

                    result = await get_or_create_daily(
                        mock_db,
                        vault_id=uuid4(),
                        vault_data={
                            "number": 1,
                            "population": 10,
                            "population_max": 20,
                            "bottle_caps": 500,
                            "happiness": 70,
                            "power": 50,
                            "power_max": 100,
                            "food": 50,
                            "food_max": 100,
                            "water": 50,
                            "water_max": 100,
                        },
                        recent_notifications=[],
                        gender_counts=[],
                    )

                    # Should still have script, audio_url should be None
                    assert result["script"] is not None
                    assert len(result["script"]) > 0
                    assert result["audio_url"] is None


class TestPostProcess:
    """Test ffmpeg post-processing fallback behavior."""

    def test_no_ffmpeg_returns_raw_wav(self):
        from app.services.broadcast_service import _post_process

        wav_bytes = b"fake wav data"
        with patch("app.services.broadcast_service.shutil.which", return_value=None):
            result = _post_process(wav_bytes)
            assert result == (wav_bytes, "audio/wav", "wav")

    def test_with_ffmpeg_available(self):
        from app.services.broadcast_service import _post_process

        wav_bytes = b"fake wav data"
        # Simulate successful ffmpeg
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b"fake mp3 data"
        with (
            patch("app.services.broadcast_service.shutil.which", return_value="/usr/bin/ffmpeg"),
            patch(
                "app.services.broadcast_service.subprocess.run",
                return_value=mock_proc,
            ) as mock_run,
        ):
            result = _post_process(wav_bytes)
            assert result == (b"fake mp3 data", "audio/mpeg", "mp3")
            command = mock_run.call_args.args[0]
            assert command[command.index("-f") + 1] == "wav"
