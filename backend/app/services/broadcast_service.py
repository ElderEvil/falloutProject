"""Broadcast service — daily broadcast lifecycle: script → TTS → post-process → upload."""

import asyncio
import logging
import shutil
import subprocess
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.broadcast import (
    clear_audio_keys,
    count_trigger_on_date,
    create_broadcast,
    get_audio_keys_before,
    get_today_broadcast,
)
from app.models.vault import Vault
from app.schemas.broadcast import BroadcastRead
from app.services.elevenlabs_service import get_elevenlabs_tts_service
from app.services.openrouter_tts_service import get_openrouter_tts_service
from app.services.storage.factory import get_storage_client
from app.utils.broadcast_script import build_daily_script
from app.utils.exceptions import (
    BroadcastRateLimitException,
    ElevenLabsProviderException,
    TTSProviderException,
    ValidationException,
)

logger = logging.getLogger(__name__)

# Rate limit: max regenerations per vault per UTC day
MAX_REGENERATIONS_PER_DAY = 3

WAV_CONTENT_TYPE = "audio/wav"
MP3_CONTENT_TYPE = "audio/mpeg"


def _utc_today() -> date:
    return datetime.now(UTC).date()


def vault_stats_from_db(vault: Vault) -> dict[str, Any]:
    """Extract vault statistics for script rendering."""
    return {
        "number": vault.number,
        "bottle_caps": vault.bottle_caps,
        "happiness": vault.happiness,
        "power": vault.power,
        "power_max": vault.power_max,
        "food": vault.food,
        "food_max": vault.food_max,
        "water": vault.water,
        "water_max": vault.water_max,
        "population_max": vault.population_max,
    }


def _post_process(wav_bytes: bytes) -> tuple[bytes, str, str]:
    """Apply vintage radio FX via ffmpeg when available.

    Returns ``(audio_bytes, content_type, extension)``. The input is a WAV file,
    so ffmpeg must be told ``-f wav``; treating the header as raw PCM would inject
    a noise burst and misalign the samples. When ffmpeg is unavailable, the WAV
    is returned unchanged with its real content type.
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        logger.info("ffmpeg not found; returning raw WAV for broadcast audio")
        return wav_bytes, WAV_CONTENT_TYPE, "wav"

    af_chain = (
        "asetrate=44100*0.93,aresample=44100,"
        "highpass=f=250,lowpass=f=4000,"
        "equalizer=f=1500:width_type=h:width=2000:g=4,"
        "flanger=delay=2:depth=1:regen=0:width=30:speed=0.4,"
        "acompressor=threshold=0.3:ratio=3,volume=1.3"
    )

    try:
        proc = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [
                ffmpeg_path,
                "-f",
                "wav",
                "-i",
                "pipe:0",
                "-af",
                af_chain,
                "-b:a",
                "128k",
                "-f",
                "mp3",
                "-",
            ],
            check=False,
            shell=False,
            input=wav_bytes,
            capture_output=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning("ffmpeg post-process failed: %s; returning raw WAV", e)
        return wav_bytes, WAV_CONTENT_TYPE, "wav"
    if proc.returncode != 0:
        logger.warning("ffmpeg post-process returned %d: %s", proc.returncode, proc.stderr[:200].decode())
        return wav_bytes, WAV_CONTENT_TYPE, "wav"
    logger.info("ffmpeg post-process applied: WAV to MP3 (%d bytes)", len(proc.stdout))
    return proc.stdout, MP3_CONTENT_TYPE, "mp3"


def _audio_url(audio_key: str | None) -> str | None:
    """Resolve a stored object key to a playable URL."""
    if not audio_key:
        return None
    client = get_storage_client()
    if client is None:
        return None
    url = client.public_url(file_name=audio_key)
    return url or None


def _delete_uploaded(audio_key: str | None) -> bool:
    if not audio_key:
        return False
    client = get_storage_client()
    if client is None:
        return False
    try:
        return bool(client.delete_file(file_name=audio_key))
    except Exception as e:
        logger.warning("Could not delete unused broadcast audio %s: %s", audio_key, e)
        return False


async def _require_vault_lock(db: AsyncSession, vault_id: UUID) -> None:
    if await crud.vault.get_for_update(db, vault_id) is None:
        raise ValidationException("Vault not found")


async def _ensure_regeneration_allowed(db: AsyncSession, vault_id: UUID, today: date) -> None:
    if await count_trigger_on_date(db, vault_id, "manual", today) >= MAX_REGENERATIONS_PER_DAY:
        raise BroadcastRateLimitException(
            detail=f"Manual regeneration limit reached ({MAX_REGENERATIONS_PER_DAY}/day for this vault).",
        )


async def delete_audio_keys(audio_keys: list[str]) -> None:
    """Best-effort object deletion for a batch of broadcast audio keys."""
    for key in audio_keys:
        await asyncio.to_thread(_delete_uploaded, key)


async def _delete_superseded(previous: Any | None, new_audio_key: str | None) -> None:
    if previous is not None and previous.audio_key and new_audio_key and previous.audio_key != new_audio_key:
        await asyncio.to_thread(_delete_uploaded, previous.audio_key)


async def _prune_older_audio_transaction(db: AsyncSession, vault_id: UUID, today: date) -> None:
    try:
        keys = await get_audio_keys_before(db, vault_id, datetime.combine(today, datetime.min.time()))
        cleared = [key for key in keys if await asyncio.to_thread(_delete_uploaded, key)]
        if not cleared:
            return
        await clear_audio_keys(db, vault_id, cleared)
        await db.commit()
    except Exception:
        logger.warning("Older broadcast audio prune failed for vault %s", vault_id, exc_info=True)
        await db.rollback()


def _serialize(broadcast: Any, *, audio_url: str | None = None) -> BroadcastRead:
    return BroadcastRead(
        id=broadcast.id,
        title=broadcast.title,
        script=broadcast.script,
        audio_url=audio_url if audio_url is not None else _audio_url(broadcast.audio_key),
        trigger=broadcast.trigger,
        created_at=broadcast.created_at,
    )


async def _recent_notifications(db: AsyncSession, vault_id: UUID) -> list[dict[str, Any]]:
    rows = await crud.notification.get_recent_for_vault(db, vault_id, limit=5)
    return [
        {
            **(row.meta_data or {}),
            "notification_type": getattr(row.notification_type, "value", row.notification_type),
            "title": row.title,
            "message": row.message,
        }
        for row in rows
    ]


async def _gender_counts(db: AsyncSession, vault_id: UUID) -> list[tuple[str, int]]:
    counts = await crud.dweller.count_living_by_gender(db, vault_id)
    return sorted(counts.items(), key=lambda item: -item[1])[:3]


async def _prepare(
    db: AsyncSession,
    vault_id: UUID,
    vault_data: dict[str, Any] | None,
    recent_notifications: list[dict[str, Any]] | None,
    gender_counts: list[tuple[str, int]] | None,
    today: date,
) -> tuple[str, str, str | None, str | None]:
    if vault_data is None:
        vault = await db.get(Vault, vault_id)
        data = vault_stats_from_db(vault) if vault is not None else {}
    else:
        data = dict(vault_data)
    if "population" not in data:
        data["population"] = await crud.vault.get_population(db_session=db, vault_id=vault_id)
    if recent_notifications is None:
        recent_notifications = await _recent_notifications(db, vault_id)
    if gender_counts is None:
        gender_counts = await _gender_counts(db, vault_id)

    title, script = build_daily_script(
        population=int(data.get("population", 0)),
        population_max=int(data.get("population_max") or 0),
        caps=int(data.get("bottle_caps", 0)),
        happiness=int(data.get("happiness", 50)),
        power=(int(data.get("power", 0)), int(data.get("power_max") or 0)),
        food=(int(data.get("food", 0)), int(data.get("food_max") or 0)),
        water=(int(data.get("water", 0)), int(data.get("water_max") or 0)),
        recent_notifications=recent_notifications,
        gender_counts=gender_counts,
        vault_number=data.get("number"),
    )

    audio_key, audio_url = await _render_audio(script, today)
    return title, script, audio_key, audio_url


async def _render_audio(script: str, today: date) -> tuple[str | None, str | None]:
    audio_bytes: bytes | None = None
    content_type = MP3_CONTENT_TYPE
    extension = "mp3"

    tts = get_openrouter_tts_service()
    if tts.is_enabled:
        try:
            wav_bytes = await tts.generate_speech(script)
            audio_bytes, content_type, extension = await asyncio.to_thread(_post_process, wav_bytes)
        except TTSProviderException as e:
            logger.warning("OpenRouter TTS failed, trying ElevenLabs: %s", e)

    if audio_bytes is None:
        eleven = get_elevenlabs_tts_service()
        if eleven.is_enabled:
            try:
                audio_bytes = await eleven.generate_speech(script)
            except ElevenLabsProviderException as e:
                logger.warning("ElevenLabs fallback failed, returning script-only: %s", e)

    if audio_bytes is None:
        logger.info("No TTS provider available, script-only broadcast")
        return None, None

    client = get_storage_client()
    if client is None:
        logger.info("Storage not enabled, returning script-only")
        return None, None

    key = f"broadcasts/{today:%Y/%m/%d}/{uuid4()}.{extension}"
    try:
        url = await asyncio.to_thread(
            client.upload_file,
            file_data=audio_bytes,
            file_name=key,
            file_type=content_type,
        )
    except Exception as e:
        logger.warning("S3 upload failed: %s; returning script-only", e)
        return None, None
    url = url or _audio_url(key)
    if not url:
        return None, None
    return key, url


async def get_or_create_daily(
    db: AsyncSession,
    vault_id: UUID,
    vault_data: dict[str, Any] | None = None,
    recent_notifications: list[dict[str, Any]] | None = None,
    gender_counts: list[tuple[str, int]] | None = None,
) -> BroadcastRead:
    """Get today's broadcast, generating it once if none exists.

    Generation happens outside the vault lock; the lock is taken only to
    re-check and insert, so a slow TTS call does not block vault operations.
    """
    today = _utc_today()

    existing = await get_today_broadcast(db, vault_id)
    if existing:
        return _serialize(existing)

    title, script, audio_key, audio_url = await _prepare(
        db, vault_id, vault_data, recent_notifications, gender_counts, today
    )

    try:
        await _require_vault_lock(db, vault_id)
        existing = await get_today_broadcast(db, vault_id)
        if existing:
            await asyncio.to_thread(_delete_uploaded, audio_key)
            return _serialize(existing)
        broadcast = await create_broadcast(
            db,
            vault_id=vault_id,
            title=title,
            script=script,
            audio_key=audio_key,
            trigger="daily",
        )
        await db.commit()
    except Exception:
        await asyncio.to_thread(_delete_uploaded, audio_key)
        raise
    await db.refresh(broadcast)
    result = _serialize(broadcast, audio_url=audio_url)
    await _prune_older_audio_transaction(db, vault_id, today)
    return result


async def regenerate(
    db: AsyncSession,
    vault_id: UUID,
    vault_data: dict[str, Any] | None = None,
    recent_notifications: list[dict[str, Any]] | None = None,
    gender_counts: list[tuple[str, int]] | None = None,
) -> BroadcastRead:
    """Render a new manual broadcast, rate-limited to three per UTC day."""
    today = _utc_today()

    await _ensure_regeneration_allowed(db, vault_id, today)

    title, script, audio_key, audio_url = await _prepare(
        db, vault_id, vault_data, recent_notifications, gender_counts, today
    )

    try:
        await _require_vault_lock(db, vault_id)
        await _ensure_regeneration_allowed(db, vault_id, today)
        previous = await get_today_broadcast(db, vault_id)
        broadcast = await create_broadcast(
            db,
            vault_id=vault_id,
            title=title,
            script=script,
            audio_key=audio_key,
            trigger="manual",
        )
        await db.commit()
    except Exception:
        await asyncio.to_thread(_delete_uploaded, audio_key)
        raise
    await db.refresh(broadcast)
    await _delete_superseded(previous, audio_key)
    result = _serialize(broadcast, audio_url=audio_url)
    await _prune_older_audio_transaction(db, vault_id, today)
    return result
