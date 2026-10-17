#!/usr/bin/env python3
"""Standalone manifest-driven voice-pack generator.

Usage:
    python scripts/generate_voices.py --dry-run
    python scripts/generate_voices.py --upload

Reads scripts/voice_manifest.json and generates MP3 files via ElevenLabs.
Skips entries whose content-keyed audio already exists locally or (with
--upload) in the dweller-audio bucket. Keys are content hashes shared with
the runtime cache-first lookup (DwellerAIService._cache_key), so a
pre-generated pack IS the runtime cache.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Bootstrap so backend/app imports resolve regardless of CWD
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_BACKEND_ROOT = _REPO_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings as _settings
from app.services.elevenlabs_service import ElevenLabsTtsService
from app.utils.narration_keys import narration_cache_key

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Environment-agnostic staging dir: backend .env NARRATION_PACK_DIR, relative
# to the repo root (never tied to any particular user's home directory).
DEFAULT_OUTPUT_DIR = _REPO_ROOT / _settings.NARRATION_PACK_DIR
MANIFEST_PATH = _REPO_ROOT / "scripts" / "voice_manifest.json"
BUCKET = "dweller-audio"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate voice pack from manifest")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip actual generation and upload; print what would be done.",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload generated files to the dweller-audio bucket after generation.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help=f"Manifest file path (default: {MANIFEST_PATH}).",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> tuple[dict[str, str], list[dict]]:
    """Load manifest; returns (voice_registry, lines).

    The voice registry is the authoritative game-side key -> ElevenLabs
    voice_id mapping. Line entries reference voices only by key; a
    per-entry ``voice_id`` override is rejected — one canonical provider
    voice per game-side voice_type, or the content cache collides.
    """
    with Path(path).open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):  # legacy format: no registry
        return {}, data
    return data.get("voices", {}), data.get("lines", [])


def resolve_voice(entry: dict, registry: dict[str, str]) -> str:
    """Resolve the entry's synthesis voice via the registry.

    Raises:
        ValueError: If the voice_type is unknown or a per-entry voice_id
            override is present (contract: registry is the only mapping).
    """
    if entry.get("voice_id"):
        raise ValueError(
            f"{entry.get('key', '<entry>')}: per-entry voice_id is forbidden — "
            "map the voice_type in the manifest's 'voices' registry instead"
        )
    voice_type = entry.get("voice_type", "echo")
    voice_id = registry.get(voice_type)
    if not voice_id:
        raise ValueError(
            f"{entry.get('key', '<entry>')}: voice_type '{voice_type}' not in manifest voice registry"
        )
    return voice_id


def content_cache_key(entry: dict) -> str:
    """Deterministic cache object key via the shared runtime helper.

    Uses the entry's runtime voice_type ("echo" unless overridden) — the
    same identifier dweller requests hash — so pre-generated pack audio IS
    the runtime cache.
    """
    text = entry["text"]
    voice_type = entry.get("voice_type", "echo")
    return narration_cache_key(text, voice_type)


def generate_entry(
    entry: dict,
    elevenlabs_svc: ElevenLabsTtsService,
    registry: dict[str, str],
) -> bytes:
    """Generate speech for one manifest entry. Raises on provider errors."""
    text = entry["text"]
    voice_id = resolve_voice(entry, registry)
    return asyncio.run(elevenlabs_svc.generate_speech(text=text, voice_id=voice_id))


def upload_entry(audio_bytes: bytes, cache_key: str, key: str) -> None:
    """Upload audio to the dweller-audio bucket under its content-cache key."""
    from app.services.storage.factory import get_storage_client

    storage = get_storage_client()
    if storage is None or not storage.enabled:
        logger.warning(
            "  [warn] Storage service unavailable; skipping upload of %s", key
        )
        return

    try:
        url = storage.upload_file(
            file_data=audio_bytes,
            file_name=cache_key,
            file_type="audio/mpeg",
            bucket_name=BUCKET,
        )
        logger.info("  [uploaded] %s → %s", key, url)
    except Exception as e:  # noqa: BLE001 - CLI boundary: report-and-continue per entry
        logger.error("  [upload-fail] %s: %s", key, e)


def remote_exists(cache_key: str, key: str) -> bool | None:
    """True/False if the bucket can be queried, None if storage is unavailable."""
    from app.services.storage.factory import get_storage_client

    storage = get_storage_client()
    if storage is None or not storage.enabled:
        return None
    try:
        return storage.file_exists(file_name=cache_key, bucket_name=BUCKET)
    except Exception as e:  # noqa: BLE001 - CLI boundary: report-and-continue per entry
        logger.warning("  [warn] Bucket lookup failed for %s: %s", key, e)
        return None


def main() -> None:
    args = parse_args()

    output_dir = args.output_dir or DEFAULT_OUTPUT_DIR
    manifest_path = args.manifest or MANIFEST_PATH

    if not manifest_path.exists():
        logger.error("Manifest not found: %s", manifest_path)
        sys.exit(1)

    # The settings instance already loads backend/.env — never overwrite it here.
    elevenlabs_svc = ElevenLabsTtsService()
    if not elevenlabs_svc.is_enabled and not args.dry_run:
        logger.warning(
            "ElevenLabs API key not configured (ELEVENLABS_API_KEY in backend/.env or environment)."
        )
        logger.warning("With --dry-run this is fine; otherwise generation will fail.")

    registry, entries = load_manifest(manifest_path)
    generated = 0
    skipped = 0
    failed = 0

    for entry in entries:
        key = entry["key"]
        cache_key = content_cache_key(entry)
        mp3_path = output_dir / cache_key.replace("pa/", "")
        try:
            # Contract check up front: every line must resolve through the
            # registry (no per-entry voice_id), or the cache contract breaks.
            resolve_voice(entry, registry)
        except ValueError as e:
            logger.error("  [invalid] %s: %s", key, e)
            failed += 1
            continue

        # Local skip is keyed by content: changed text/voice regenerates.
        has_local = mp3_path.exists()
        has_remote = remote_exists(cache_key, key) if args.upload else None

        if args.dry_run:
            if has_local or has_remote:
                logger.info(
                    "  [skip] %s (%s exists)", key, "local" if has_local else "bucket"
                )
                skipped += 1
            else:
                logger.info(
                    "  [dry-run] Would generate: %s → %s", key, entry["text"][:60]
                )
                generated += 1
            continue

        if has_remote:
            # Bucket already has the content-keyed audio; just mirror it locally
            # if missing, so later --upload runs don't spend credits.
            output_dir.mkdir(parents=True, exist_ok=True)
            if not has_local:
                from app.services.storage.factory import get_storage_client

                storage = get_storage_client()
                data = storage.download_file(file_name=cache_key, bucket_name=BUCKET)
                mp3_path.write_bytes(data)
                logger.info("  [mirrored] %s ← bucket", key)
            else:
                logger.info("  [skip] %s (bucket has it)", key)
            skipped += 1
            continue

        if has_local:
            # Generated locally before but never uploaded: upload without regenerating.
            if args.upload:
                logger.info("  [upload-only] %s", key)
                upload_entry(mp3_path.read_bytes(), cache_key, key)
            else:
                logger.info("  [skip] %s (already exists)", key)
            skipped += 1
            continue

        try:
            audio_bytes = generate_entry(entry, elevenlabs_svc, registry)
        except Exception as e:  # noqa: BLE001 - CLI boundary: report-and-continue per entry
            logger.error("  [error] %s: %s", key, e)
            failed += 1
            continue

        output_dir.mkdir(parents=True, exist_ok=True)
        mp3_path.write_bytes(audio_bytes)
        logger.info("  [generated] %s → %s", key, mp3_path)
        generated += 1

        if args.upload:
            upload_entry(audio_bytes, cache_key, key)

    print(
        f"\nSummary: {generated} generated, {skipped} skipped, {failed} failed out of {len(entries)} entries"
    )


if __name__ == "__main__":
    main()
