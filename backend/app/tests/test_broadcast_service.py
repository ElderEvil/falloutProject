from contextlib import ExitStack, asynccontextmanager, contextmanager
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
from app.utils.exceptions import (
    BroadcastNotYetAiringException,
    BroadcastRateLimitException,
    TTSProviderException,
)

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


@contextmanager
def _pipeline(*, openrouter: MagicMock | None = None, elevenlabs: MagicMock | None = None, storage=None):
    with ExitStack() as stack:
        for name, service in (
            ("get_openrouter_tts_service", openrouter),
            ("get_elevenlabs_tts_service", elevenlabs),
        ):
            fallback = _tts(enabled=False)
            stack.enter_context(patch.object(broadcast_service, name, return_value=service or fallback))
        stack.enter_context(patch.object(broadcast_service, "get_storage_client", return_value=storage))
        stack.enter_context(patch("app.services.broadcast_service.shutil.which", return_value=None))
        yield


async def _daily_row(db, vault, audio_key: str | None = None, *, days_ago: int = 0) -> Broadcast:
    row = await create_broadcast(db, vault_id=vault.id, title="Old", script="Old script", audio_key=audio_key)
    row.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_ago)
    await db.commit()
    return row


@asynccontextmanager
async def _fail_sql(async_session, predicate, message: str):
    connection = (await async_session.connection()).sync_connection

    def hook(_conn, _cursor, statement, _parameters, _context, _many):
        if predicate(statement):
            raise RuntimeError(message)

    event.listen(connection, "before_cursor_execute", hook)
    try:
        yield
    finally:
        event.remove(connection, "before_cursor_execute", hook)


def _selects_vault(statement: str) -> bool:
    normalized = statement.lower()
    return normalized.startswith("select") and "from vault" in normalized and "where vault.id" in normalized


def _selects_broadcast(statement: str) -> bool:
    normalized = statement.lower()
    return normalized.startswith("select") and "from broadcast" in normalized and "where broadcast.id" in normalized


async def test_daily_broadcast_created_once(async_session, vault):
    with _pipeline():
        first = await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)
        second = await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)
    rows = (await async_session.exec(select(Broadcast))).all()
    assert ((first.id, len(rows)), rows[0].trigger) == ((second.id, 1), "daily")


async def test_daily_broadcast_waits_until_the_day_after_founding(async_session, vault):
    with _pipeline():
        result = await get_or_create_daily(
            async_session,
            vault.id,
            vault_data=VAULT_DATA,
            vault_created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    rows = (await async_session.exec(select(Broadcast))).all()
    assert (result, rows) == (None, [])


async def test_daily_broadcast_airs_once_the_vault_is_a_day_old(async_session, vault):
    with _pipeline():
        result = await get_or_create_daily(
            async_session,
            vault.id,
            vault_data=VAULT_DATA,
            vault_created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1),
        )
    assert result is not None
    assert result.trigger == "daily"


async def test_regenerate_before_the_first_airing_is_refused(async_session, vault):
    with _pipeline(), pytest.raises(BroadcastNotYetAiringException):
        await regenerate(
            async_session,
            vault.id,
            vault_data=VAULT_DATA,
            vault_created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    rows = (await async_session.exec(select(Broadcast))).all()
    assert rows == []


async def test_daily_broadcast_without_explicit_context_uses_vault_stats(async_session, vault):
    with _pipeline():
        result = await get_or_create_daily(async_session, vault.id)
    assert f"Vault {vault.number}" in result.script
    assert f"{vault.bottle_caps:,}" in result.script
    assert "Vault the vault" not in result.script


async def test_regenerate_creates_manual_rows_and_enforces_cap(async_session, vault):
    with _pipeline():
        for _ in range(MAX_REGENERATIONS_PER_DAY):
            result = await regenerate(async_session, vault.id, vault_data=VAULT_DATA)
            assert result.trigger == "manual"
        with pytest.raises(BroadcastRateLimitException):
            await regenerate(async_session, vault.id, vault_data=VAULT_DATA)
    rows = (await async_session.exec(select(Broadcast))).all()
    assert len(rows) == MAX_REGENERATIONS_PER_DAY


async def test_tts_failure_falls_back_to_script_only(async_session, vault):
    with _pipeline(openrouter=_tts(enabled=True, error=TTSProviderException("down"))):
        result = await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)
    assert result.audio_url is None
    assert result.script


async def test_elevenlabs_fallback_uploads_audio(async_session, vault):
    client = _storage()
    with _pipeline(
        openrouter=_tts(enabled=True, error=TTSProviderException("down")),
        elevenlabs=_tts(enabled=True, audio=b"mp3"),
        storage=client,
    ):
        result = await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)
    assert result.audio_url == "https://cdn/audio.mp3"
    client.upload_file.assert_called_once()
    assert client.upload_file.call_args.kwargs["bucket_name"] == broadcast_service.BROADCAST_AUDIO_BUCKET


async def test_cached_audio_url_resolves_public_url(async_session, vault):
    await _daily_row(async_session, vault, "broadcasts/old.mp3")
    client = _storage("https://cdn/broadcasts/old.mp3")
    with _pipeline(storage=client):
        result = await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)
    assert result.audio_url == "https://cdn/broadcasts/old.mp3"
    client.public_url.assert_called_with(
        file_name="broadcasts/old.mp3", bucket_name=broadcast_service.BROADCAST_AUDIO_BUCKET
    )


async def test_superseded_audio_is_deleted_on_regenerate(async_session, vault):
    await _daily_row(async_session, vault, "broadcasts/old.mp3")
    client = _storage()
    with _pipeline(openrouter=_tts(enabled=True, audio=b"wav"), storage=client):
        await regenerate(async_session, vault.id, vault_data=VAULT_DATA)
    client.delete_file.assert_called_with(
        file_name="broadcasts/old.mp3", bucket_name=broadcast_service.BROADCAST_AUDIO_BUCKET
    )


async def test_older_day_audio_is_pruned_and_key_cleared(async_session, vault):
    older = await _daily_row(async_session, vault, "broadcasts/yesterday.mp3", days_ago=1)
    client = _storage()
    with _pipeline(storage=client):
        await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)
    client.delete_file.assert_called_with(
        file_name="broadcasts/yesterday.mp3", bucket_name=broadcast_service.BROADCAST_AUDIO_BUCKET
    )
    await async_session.refresh(older)
    assert older.audio_key is None


async def test_second_prune_skips_cleared_keys(async_session, vault):
    await _daily_row(async_session, vault, "broadcasts/yesterday.mp3", days_ago=1)
    client = _storage()
    with _pipeline(storage=client):
        await regenerate(async_session, vault.id, vault_data=VAULT_DATA)
        client.delete_file.reset_mock()
        await regenerate(async_session, vault.id, vault_data=VAULT_DATA)
    client.delete_file.assert_not_called()


async def test_failed_prune_keeps_key_for_retry(async_session, vault):
    older = await _daily_row(async_session, vault, "broadcasts/yesterday.mp3", days_ago=1)
    client = _storage()
    client.delete_file.side_effect = RuntimeError("storage down")
    with _pipeline(storage=client):
        await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)
    await async_session.refresh(older)
    assert older.audio_key == "broadcasts/yesterday.mp3"


async def test_clear_failure_rolls_back_prune(async_session, vault):
    older = await _daily_row(async_session, vault, "broadcasts/yesterday.mp3", days_ago=1)
    async with _fail_sql(async_session, lambda s: s.startswith("UPDATE broadcast"), "clear failed"):
        with _pipeline(storage=_storage()):
            await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)
    await async_session.refresh(older)
    assert older.audio_key == "broadcasts/yesterday.mp3"


async def test_lock_failure_deletes_uploaded_audio(async_session, vault):
    client = _storage()
    async with _fail_sql(async_session, _selects_vault, "lock failed"):
        with (
            _pipeline(openrouter=_tts(enabled=True, audio=b"wav"), storage=client),
            pytest.raises(RuntimeError, match="lock failed"),
        ):
            await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)
    assert client.delete_file.call_count == 1


async def test_refresh_failure_does_not_delete_committed_audio(async_session, vault):
    client = _storage()
    async with _fail_sql(async_session, _selects_broadcast, "refresh failed"):
        with (
            _pipeline(openrouter=_tts(enabled=True, audio=b"wav"), storage=client),
            pytest.raises(RuntimeError, match="refresh failed"),
        ):
            await get_or_create_daily(async_session, vault.id, vault_data=VAULT_DATA)
    rows = (await async_session.exec(select(Broadcast))).all()
    assert len(rows) == 1
    assert rows[0].audio_key is not None
    client.delete_file.assert_not_called()


async def test_insert_failure_rolls_back_and_deletes_upload(async_session, vault):
    client = _storage()
    async with _fail_sql(async_session, lambda s: s.startswith("INSERT INTO broadcast"), "late broadcast write failed"):
        with (
            _pipeline(openrouter=_tts(enabled=True, audio=b"wav"), storage=client),
            pytest.raises(RuntimeError, match="late broadcast write failed"),
        ):
            await regenerate(async_session, vault.id, vault_data=VAULT_DATA)
    await async_session.rollback()
    assert ((await async_session.exec(select(Broadcast))).all(), client.delete_file.call_count) == ([], 1)


def test_no_ffmpeg_returns_raw_wav():
    with patch("app.services.broadcast_service.shutil.which", return_value=None):
        assert broadcast_service._post_process(b"wav") == (b"wav", "audio/wav", "wav")


def test_with_ffmpeg_uses_wav_input():
    proc = MagicMock(returncode=0, stdout=b"mp3")
    with (
        patch("app.services.broadcast_service.shutil.which", return_value="/usr/bin/ffmpeg"),
        patch("app.services.broadcast_service.subprocess.run", return_value=proc) as run,
    ):
        assert broadcast_service._post_process(b"wav") == (b"mp3", "audio/mpeg", "mp3")
    command = run.call_args.args[0]
    assert command[command.index("-f") + 1] == "wav"
