"""Broadcast service tests on the real session; only TTS and storage are stubbed."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import event
from sqlmodel import select

from app.crud.broadcast import create_broadcast
from app.models.broadcast import Broadcast
from app.services import broadcast_service
from app.services.broadcast_service import (
    MAX_REGENERATIONS_PER_DAY,
    get_or_create_daily,
    regenerate,
    vault_stats_from_db,
)
from app.utils.exceptions import BroadcastRateLimitException, TTSProviderException

VAULT_DATA = {
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
}


def _tts(enabled: bool, *, error: Exception | None = None, audio: bytes = b"audio") -> MagicMock:
    service = MagicMock()
    service.is_enabled = enabled
    service.generate_speech = AsyncMock(side_effect=error) if error else AsyncMock(return_value=audio)
    return service


def _storage(url: str = "https://cdn/audio.mp3") -> MagicMock:
    client = MagicMock()
    client.upload_file.return_value = url
    client.public_url.return_value = url
    client.delete_file.return_value = True
    return client


async def _daily_row(db, vault, audio_key: str | None = None, *, days_ago: int = 0) -> Broadcast:
    row = await create_broadcast(db, vault_id=vault.id, title="Old", script="Old script", audio_key=audio_key)
    row.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_ago)
    await db.commit()
    return row


@pytest.mark.asyncio
async def test_daily_broadcast_created_once(async_session, vault):
    with (
        patch.object(broadcast_service, "get_openrouter_tts_service", return_value=_tts(enabled=False)),
        patch.object(broadcast_service, "get_elevenlabs_tts_service", return_value=_tts(enabled=False)),
        patch.object(broadcast_service, "get_storage_client", return_value=None),
    ):
        first = await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)
        second = await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)

    rows = (await async_session.exec(select(Broadcast))).all()
    assert first.id == second.id
    assert len(rows) == 1
    assert rows[0].trigger == "daily"


@pytest.mark.asyncio
async def test_daily_broadcast_without_explicit_context_uses_vault_stats(async_session, vault):
    with (
        patch.object(broadcast_service, "get_openrouter_tts_service", return_value=_tts(enabled=False)),
        patch.object(broadcast_service, "get_elevenlabs_tts_service", return_value=_tts(enabled=False)),
        patch.object(broadcast_service, "get_storage_client", return_value=None),
    ):
        result = await get_or_create_daily(async_session, vault.id)

    assert f"Vault {vault.number}" in result.script
    assert f"{vault.bottle_caps:,}" in result.script
    assert "Vault the vault" not in result.script


@pytest.mark.asyncio
async def test_regenerate_creates_manual_rows_and_enforces_cap(async_session, vault):
    with (
        patch.object(broadcast_service, "get_openrouter_tts_service", return_value=_tts(enabled=False)),
        patch.object(broadcast_service, "get_elevenlabs_tts_service", return_value=_tts(enabled=False)),
        patch.object(broadcast_service, "get_storage_client", return_value=None),
    ):
        for _ in range(MAX_REGENERATIONS_PER_DAY):
            result = await regenerate(async_session, vault.id, vault_data=VAULT_DATA)
            assert result.trigger == "manual"
        with pytest.raises(BroadcastRateLimitException):
            await regenerate(async_session, vault.id, vault_data=VAULT_DATA)

    rows = (await async_session.exec(select(Broadcast))).all()
    assert len(rows) == MAX_REGENERATIONS_PER_DAY


@pytest.mark.asyncio
async def test_tts_failure_falls_back_to_script_only(async_session, vault):
    openrouter = _tts(enabled=True, error=TTSProviderException("down"))
    with (
        patch.object(broadcast_service, "get_openrouter_tts_service", return_value=openrouter),
        patch.object(broadcast_service, "get_elevenlabs_tts_service", return_value=_tts(enabled=False)),
        patch.object(broadcast_service, "get_storage_client", return_value=None),
    ):
        result = await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)

    assert result.audio_url is None
    assert result.script


@pytest.mark.asyncio
async def test_elevenlabs_fallback_uploads_audio(async_session, vault):
    client = _storage()
    with (
        patch.object(
            broadcast_service,
            "get_openrouter_tts_service",
            return_value=_tts(enabled=True, error=TTSProviderException("down")),
        ),
        patch.object(broadcast_service, "get_elevenlabs_tts_service", return_value=_tts(enabled=True, audio=b"mp3")),
        patch.object(broadcast_service, "get_storage_client", return_value=client),
    ):
        result = await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)

    assert result.audio_url == "https://cdn/audio.mp3"
    client.upload_file.assert_called_once()


@pytest.mark.asyncio
async def test_cached_audio_url_resolves_public_url(async_session, vault):
    await _daily_row(async_session, vault, "broadcasts/old.mp3")
    client = _storage("https://cdn/broadcasts/old.mp3")
    with patch.object(broadcast_service, "get_storage_client", return_value=client):
        result = await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)

    assert result.audio_url == "https://cdn/broadcasts/old.mp3"


@pytest.mark.asyncio
async def test_superseded_audio_is_deleted_on_regenerate(async_session, vault):
    await _daily_row(async_session, vault, "broadcasts/old.mp3")
    client = _storage()
    with (
        patch.object(broadcast_service, "get_openrouter_tts_service", return_value=_tts(enabled=True, audio=b"wav")),
        patch.object(broadcast_service, "get_elevenlabs_tts_service", return_value=_tts(enabled=False)),
        patch.object(broadcast_service, "get_storage_client", return_value=client),
        patch("app.services.broadcast_service.shutil.which", return_value=None),
    ):
        await regenerate(async_session, vault.id, vault_data=VAULT_DATA)

    client.delete_file.assert_called_with(file_name="broadcasts/old.mp3")


@pytest.mark.asyncio
async def test_older_day_audio_is_pruned_and_key_cleared(async_session, vault):
    older = await _daily_row(async_session, vault, "broadcasts/yesterday.mp3", days_ago=1)
    client = _storage()
    with (
        patch.object(broadcast_service, "get_openrouter_tts_service", return_value=_tts(enabled=False)),
        patch.object(broadcast_service, "get_elevenlabs_tts_service", return_value=_tts(enabled=False)),
        patch.object(broadcast_service, "get_storage_client", return_value=client),
    ):
        await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)

    client.delete_file.assert_called_with(file_name="broadcasts/yesterday.mp3")
    await async_session.refresh(older)
    assert older.audio_key is None


@pytest.mark.asyncio
async def test_second_prune_skips_cleared_keys(async_session, vault):
    await _daily_row(async_session, vault, "broadcasts/yesterday.mp3", days_ago=1)
    client = _storage()
    with (
        patch.object(broadcast_service, "get_openrouter_tts_service", return_value=_tts(enabled=False)),
        patch.object(broadcast_service, "get_elevenlabs_tts_service", return_value=_tts(enabled=False)),
        patch.object(broadcast_service, "get_storage_client", return_value=client),
    ):
        await regenerate(async_session, vault.id, vault_data=VAULT_DATA)
        client.delete_file.reset_mock()
        await regenerate(async_session, vault.id, vault_data=VAULT_DATA)

    client.delete_file.assert_not_called()


@pytest.mark.asyncio
async def test_failed_prune_keeps_key_for_retry(async_session, vault):
    older = await _daily_row(async_session, vault, "broadcasts/yesterday.mp3", days_ago=1)
    client = _storage()
    client.delete_file.side_effect = RuntimeError("storage down")
    with (
        patch.object(broadcast_service, "get_openrouter_tts_service", return_value=_tts(enabled=False)),
        patch.object(broadcast_service, "get_elevenlabs_tts_service", return_value=_tts(enabled=False)),
        patch.object(broadcast_service, "get_storage_client", return_value=client),
    ):
        await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)

    await async_session.refresh(older)
    assert older.audio_key == "broadcasts/yesterday.mp3"


@pytest.mark.asyncio
async def test_clear_failure_rolls_back_prune(async_session, vault):
    older = await _daily_row(async_session, vault, "broadcasts/yesterday.mp3", days_ago=1)
    client = _storage()
    connection = (await async_session.connection()).sync_connection

    def fail_clear(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.startswith("UPDATE broadcast"):
            raise RuntimeError("clear failed")

    event.listen(connection, "before_cursor_execute", fail_clear)
    try:
        with (
            patch.object(broadcast_service, "get_openrouter_tts_service", return_value=_tts(enabled=False)),
            patch.object(broadcast_service, "get_elevenlabs_tts_service", return_value=_tts(enabled=False)),
            patch.object(broadcast_service, "get_storage_client", return_value=client),
        ):
            await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)
    finally:
        event.remove(connection, "before_cursor_execute", fail_clear)

    await async_session.refresh(older)
    assert older.audio_key == "broadcasts/yesterday.mp3"


@pytest.mark.asyncio
async def test_lock_failure_deletes_uploaded_audio(async_session, vault):
    client = _storage()
    connection = (await async_session.connection()).sync_connection

    def fail_lock(_conn, _cursor, statement, _parameters, _context, _many):
        normalized = statement.lower()
        if normalized.startswith("select") and "from vault" in normalized and "where vault.id" in normalized:
            raise RuntimeError("lock failed")

    event.listen(connection, "before_cursor_execute", fail_lock)
    try:
        with (
            patch.object(
                broadcast_service, "get_openrouter_tts_service", return_value=_tts(enabled=True, audio=b"wav")
            ),
            patch.object(broadcast_service, "get_elevenlabs_tts_service", return_value=_tts(enabled=False)),
            patch.object(broadcast_service, "get_storage_client", return_value=client),
            patch("app.services.broadcast_service.shutil.which", return_value=None),
            pytest.raises(RuntimeError, match="lock failed"),
        ):
            await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)
    finally:
        event.remove(connection, "before_cursor_execute", fail_lock)

    assert client.delete_file.call_count == 1


@pytest.mark.asyncio
async def test_refresh_failure_does_not_delete_committed_audio(async_session, vault):
    client = _storage()
    connection = (await async_session.connection()).sync_connection

    def fail_refresh(_conn, _cursor, statement, _parameters, _context, _many):
        normalized = statement.lower()
        if normalized.startswith("select") and "from broadcast" in normalized and "where broadcast.id" in normalized:
            raise RuntimeError("refresh failed")

    event.listen(connection, "before_cursor_execute", fail_refresh)
    try:
        with (
            patch.object(
                broadcast_service, "get_openrouter_tts_service", return_value=_tts(enabled=True, audio=b"wav")
            ),
            patch.object(broadcast_service, "get_elevenlabs_tts_service", return_value=_tts(enabled=False)),
            patch.object(broadcast_service, "get_storage_client", return_value=client),
            patch("app.services.broadcast_service.shutil.which", return_value=None),
            pytest.raises(RuntimeError, match="refresh failed"),
        ):
            await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)
    finally:
        event.remove(connection, "before_cursor_execute", fail_refresh)

    rows = (await async_session.exec(select(Broadcast))).all()
    assert len(rows) == 1
    assert rows[0].audio_key is not None
    client.delete_file.assert_not_called()


@pytest.mark.asyncio
async def test_insert_failure_rolls_back_and_deletes_upload(async_session, vault):
    client = _storage()
    connection = (await async_session.connection()).sync_connection

    def fail_broadcast_insert(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.startswith("INSERT INTO broadcast"):
            raise RuntimeError("late broadcast write failed")

    event.listen(connection, "before_cursor_execute", fail_broadcast_insert)
    try:
        with (
            patch.object(
                broadcast_service, "get_openrouter_tts_service", return_value=_tts(enabled=True, audio=b"wav")
            ),
            patch.object(broadcast_service, "get_elevenlabs_tts_service", return_value=_tts(enabled=False)),
            patch.object(broadcast_service, "get_storage_client", return_value=client),
            patch("app.services.broadcast_service.shutil.which", return_value=None),
            pytest.raises(RuntimeError, match="late broadcast write failed"),
        ):
            await regenerate(async_session, vault.id, vault_data=VAULT_DATA)
    finally:
        event.remove(connection, "before_cursor_execute", fail_broadcast_insert)

    await async_session.rollback()
    assert (await async_session.exec(select(Broadcast))).all() == []
    assert client.delete_file.call_count == 1


class TestPostProcess:
    def test_no_ffmpeg_returns_raw_wav(self):
        with patch("app.services.broadcast_service.shutil.which", return_value=None):
            assert broadcast_service._post_process(b"wav") == (b"wav", "audio/wav", "wav")

    def test_with_ffmpeg_uses_wav_input(self):
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = b"mp3"
        with (
            patch("app.services.broadcast_service.shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("app.services.broadcast_service.subprocess.run", return_value=proc) as run,
        ):
            assert broadcast_service._post_process(b"wav") == (b"mp3", "audio/mpeg", "mp3")
        command = run.call_args.args[0]
        assert command[command.index("-f") + 1] == "wav"
