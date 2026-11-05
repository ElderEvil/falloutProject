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

            # First call: no existing broadcast
            mock_result = MagicMock()
            mock_result.first.return_value = None
            mock_db.execute = AsyncMock(return_value=mock_result)

            await get_or_create_daily(
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

            # First call should have called TTS
            mock_service.generate_speech.assert_called_once()

            # Reset the call count
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

            mock_result2 = MagicMock()
            mock_result2.first.return_value = mock_existing
            mock_db.execute = AsyncMock(return_value=mock_result2)

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
            assert result["audio_url"] == "broadcasts/2026/11/05/test.mp3"


class TestRegenerateCap:
    """Rate limit: max 3 manual regenerations per UTC day per vault."""

    @pytest.mark.asyncio
    async def test_regenerate_exceeds_cap(self):
        from app.services.broadcast_service import regenerate

        mock_db = AsyncMock()

        # Simulate 3 existing manual regenerations today
        mock_result = MagicMock()
        mock_rows = [MagicMock() for _ in range(3)]
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(Exception) as exc_info:
            await regenerate(mock_db, vault_id=uuid4())
        assert "limit reached" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_regenerate_under_cap_proceeds(self):
        from app.services import broadcast_service
        from app.services.broadcast_service import regenerate

        mock_db = AsyncMock()

        # Simulate 2 existing manual regenerations (under cap)
        mock_result = MagicMock()
        mock_rows = [MagicMock() for _ in range(2)]
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute = AsyncMock(return_value=mock_result)

        # First call for create
        mock_create_result = MagicMock()
        mock_create_result.first.return_value = None
        mock_db.execute.side_effect = [mock_result, mock_create_result]

        # Simulate db.add/commit/refresh
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

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
            )
            assert result is not None
            assert result["trigger"] == "daily"


class TestTTSFailureDegradation:
    """When TTS fails, the endpoint returns script-only (never 500)."""

    @pytest.mark.asyncio
    async def test_tts_failure_returns_script_only(self):
        from app.services import broadcast_service
        from app.services.broadcast_service import get_or_create_daily
        from app.utils.exceptions import TTSProviderException

        mock_db = AsyncMock()

        # No existing broadcast
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

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
            assert result == wav_bytes

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
            ),
        ):
            result = _post_process(wav_bytes)
            assert result == b"fake mp3 data"
