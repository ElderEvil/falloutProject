"""Broadcast service — daily broadcast lifecycle: script → TTS → post-process → upload."""

import logging
import shutil
import subprocess
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.broadcast import Broadcast
from app.services.broadcast_script_service import build_daily_script
from app.services.openrouter_tts_service import get_openrouter_tts_service
from app.services.storage.factory import get_storage_client
from app.utils.exceptions import TTSProviderException

logger = logging.getLogger(__name__)

# Rate limit: max regenerations per vault per UTC day
MAX_REGENERATIONS_PER_DAY = 3


def _post_process(wav_bytes: bytes) -> bytes:
    """Apply vintage radio FX via ffmpeg when available.

    Corrected chain (per prototype validation):
    - asetrate 44100*0.93  → tape-speed wobble
    - aresample 44100       → resample back
    - highpass 250, lowpass 4000 → AM band-pass
    - equalizer 1500 Hz +4 dB → voice band emphasis
    - flanger → subtle chorus/space
    - acompressor + volume boost → loudness glue

    Note: loudnorm intentionally omitted for MVP simplicity (validated
    in prototype).  No noise bed or CC0 static — that's a follow-up
    enhancement.

    Returns WAV bytes unchanged when ffmpeg is absent.
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        logger.info("ffmpeg not found; returning raw WAV for broadcast audio")
        return wav_bytes

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
                "-f", "s16le", "-ar", "44100", "-ac", "1",
                "-i", "pipe:0",
                "-af", af_chain,
                "-b:a", "128k",
                "-f", "mp3",
                "-",
            ],
            check=False, shell=False, input=wav_bytes,
            capture_output=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning("ffmpeg post-process failed: %s; returning raw WAV", e)
        return wav_bytes
    if proc.returncode != 0:
        logger.warning("ffmpeg post-process returned %d: %s", proc.returncode, proc.stderr[:200].decode())
        return wav_bytes
    logger.info("ffmpeg post-process applied: WAV to MP3 (%d bytes)", len(proc.stdout))
    return proc.stdout


async def get_or_create_daily(
    db: AsyncSession,
    vault_id: UUID,
    vault_data: dict[str, Any] | None = None,
    dweller_stats: list[dict] | None = None,
    recent_notifications: list[dict] | None = None,
) -> dict[str, Any]:
    """Get today's broadcast or create one from scratch.

    Uses UTC day caching: once a broadcast exists for today, subsequent
    calls return it without re-calling TTS.

    Args:
        db: Database session.
        vault_id: Vault to generate for.
        vault_data: Dict with vault stats (population, caps, etc.).
        dweller_stats: Dweller data for gender splits.
        recent_notifications: Recent notification records.

    Returns:
        Dict with keys: id, title, script, audio_url, trigger, created_at.
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)
    today_start = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
    tomorrow_start = datetime.combine(tomorrow, datetime.min.time(), tzinfo=UTC)

    # Check for existing daily broadcast for today
    existing = await db.execute(
        Broadcast.__table__.select().where(
            Broadcast.vault_id == vault_id,
            Broadcast.trigger == "daily",
            Broadcast.created_at >= today_start,
            Broadcast.created_at < tomorrow_start,
        )
    )
    broadcast_row = existing.first()

    if broadcast_row:
        return {
            "id": str(broadcast_row.id),
            "title": broadcast_row.title,
            "script": broadcast_row.script,
            "audio_url": broadcast_row.audio_key,
            "trigger": "daily",
            "created_at": broadcast_row.created_at.isoformat() if broadcast_row.created_at else None,
        }

    # Build script
    vd = vault_data or {}
    ds = dweller_stats or []
    rn = recent_notifications or []

    pop = vd.get("population", 0)
    pop_max = vd.get("population_max") or 0
    caps = vd.get("bottle_caps", 0)
    happiness = vd.get("happiness", 50)
    power = (vd.get("power", 0), vd.get("power_max") or 1)
    food = (vd.get("food", 0), vd.get("food_max") or 1)
    water = (vd.get("water", 0), vd.get("water_max") or 1)

    title, script_text = build_daily_script(
        population=pop,
        population_max=pop_max,
        caps=caps,
        happiness=happiness,
        power=power,
        food=food,
        water=water,
        recent_notifications=rn,
        vault_number=vd.get("number"),
    )

    audio_url = None
    audio_key = None

    # Try TTS
    tts = get_openrouter_tts_service()
    if tts.is_enabled:
        try:
            wav_bytes = await tts.generate_speech(script_text)
            audio_processed = _post_process(wav_bytes)
        except TTSProviderException as e:
            logger.warning("TTS generation failed, falling back to script-only: %s", e)
            audio_processed = None
    else:
        logger.info("No TTS provider enabled, script-only broadcast")
        audio_processed = None

    if audio_processed:
        # Upload to S3
        day_prefix = today.strftime("%Y/%m/%d")
        key = f"broadcasts/{day_prefix}/{uuid4()}.mp3"
        storage_client = get_storage_client()
        if storage_client:
            try:
                audio_url = storage_client.upload_file(
                    file_data=audio_processed,
                    file_name=key,
                    file_type="audio/mpeg",
                )
                audio_key = key
            except Exception as e:
                logger.warning("S3 upload failed: %s; returning script-only", e)
                audio_url = None
        else:
            logger.info("Storage not enabled, returning script-only")

    # Persist broadcast
    broadcast = Broadcast(
        id=uuid4(),
        vault_id=vault_id,
        title=title,
        script=script_text,
        audio_key=audio_key,
        trigger="daily",
    )
    db.add(broadcast)
    await db.commit()
    await db.refresh(broadcast)

    return {
        "id": str(broadcast.id),
        "title": broadcast.title,
        "script": broadcast.script,
        "audio_url": audio_url,
        "trigger": "daily",
        "created_at": broadcast.created_at.isoformat() if broadcast.created_at else None,
    }


async def regenerate(
    db: AsyncSession,
    vault_id: UUID,
    vault_data: dict[str, Any] | None = None,
    dweller_stats: list[dict] | None = None,
    recent_notifications: list[dict] | None = None,
) -> dict[str, Any]:
    """Manually re-render a broadcast for the vault, rate-limited to 3/day.

    Args:
        db: Database session.
        vault_id: Vault to regenerate for.
        vault_data: Vault stats dict.
        dweller_stats: Dweller data.
        recent_notifications: Recent notifications.

    Returns:
        Same shape as get_or_create_daily.

    Raises:
        TTSProviderException: If rate limit exceeded (mapped to 429).
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)
    today_start = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
    tomorrow_start = datetime.combine(tomorrow, datetime.min.time(), tzinfo=UTC)

    # Count manual regenerations today
    count_result = await db.execute(
        Broadcast.__table__.select().where(
            Broadcast.vault_id == vault_id,
            Broadcast.trigger == "manual",
            Broadcast.created_at >= today_start,
            Broadcast.created_at < tomorrow_start,
        )
    )
    regen_count = len(count_result.fetchall())

    if regen_count >= MAX_REGENERATIONS_PER_DAY:
        raise TTSProviderException(
            detail=f"Manual regeneration limit reached ({MAX_REGENERATIONS_PER_DAY}/day for this vault).",
        )

    return await get_or_create_daily(
        db, vault_id, vault_data, dweller_stats, recent_notifications,
    )
