#!/usr/bin/env python3
"""Standalone manifest-driven voice-pack generator.

Usage:
    python scripts/generate_voices.py --dry-run
    python scripts/generate_voices.py --upload

Reads scripts/voice_manifest.json and generates MP3 files via ElevenLabs.
Skips entries already generated. With --upload also pushes to the dweller-audio bucket.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Bootstrap so backend/app imports resolve regardless of CWD
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_BACKEND_ROOT = _REPO_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings as _core_settings
from app.services.elevenlabs_service import (
    DEFAULT_MODEL_ID,
    DEFAULT_VOICE_ID,
    ElevenLabsTtsService,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path.home() / ".hermes" / "state" / "voice-pack"
MANIFEST_PATH = _REPO_ROOT / "scripts" / "voice_manifest.json"


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


def load_manifest(path: Path) -> list[dict]:
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def skip_if_exists(output_dir: Path, entry: dict, key: str) -> bool:
    """Return True if the output file already exists (skip)."""
    mp3_path = output_dir / f"{key}.mp3"
    return mp3_path.exists()


def generate_entry(
    entry: dict,
    elevenlabs_svc: ElevenLabsTtsService,
    *,
    dry_run: bool,
) -> tuple[bytes | None, str]:
    """Generate speech for one manifest entry. Returns (bytes_or_None, error_message)."""
    key = entry["key"]
    text = entry["text"]
    voice_id = entry.get("voice_id", DEFAULT_VOICE_ID)

    if dry_run:
        logger.info("  [dry-run] Would generate: %s → %s", key, text[:60])
        return b"", ""

    try:
        audio_bytes = elevenlabs_svc.generate_speech(
            text=text, voice_id=voice_id, model_id=DEFAULT_MODEL_ID
        )
        return audio_bytes, ""
    except Exception as e:  # noqa: BLE001 - CLI boundary: report-and-continue per entry
        logger.error("  [error] %s: %s", key, e)
        return None, str(e)


def upload_entry(entry: dict, audio_bytes: bytes, key: str) -> None:
    """Upload audio to the dweller-audio bucket via storage service."""
    # Lazy-import the storage client
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
            file_name=f"{key}.mp3",
            file_type="audio/mpeg",
            bucket_name="dweller-audio",
        )
        logger.info("  [uploaded] %s → %s", key, url)
    except Exception as e:  # noqa: BLE001 - CLI boundary: report-and-continue per entry
        logger.error("  [upload-fail] %s: %s", key, e)


def main() -> None:
    args = parse_args()

    output_dir = args.output_dir or DEFAULT_OUTPUT_DIR
    manifest_path = args.manifest or MANIFEST_PATH

    if not manifest_path.exists():
        logger.error("Manifest not found: %s", manifest_path)
        sys.exit(1)

    # Force a minimal core settings so the backend can run
    # (real API keys come from environment / .env, never from this script)
    _core_settings.ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")

    elevenlabs_svc = ElevenLabsTtsService()
    if not elevenlabs_svc.is_enabled and not args.dry_run:
        logger.warning(
            "ElevenLabs API key not configured. Set ELEVENLABS_API_KEY in the environment."
        )
        logger.warning("With --dry-run this is fine; otherwise generation will fail.")

    entries = load_manifest(manifest_path)
    generated = 0
    skipped = 0
    failed = 0

    for entry in entries:
        key = entry["key"]

        if args.dry_run:
            if skip_if_exists(output_dir, entry, key):
                logger.info("  [skip] %s (already exists)", key)
                skipped += 1
            else:
                _, err = generate_entry(entry, elevenlabs_svc, dry_run=True)
                if err:
                    logger.error("  [error] %s: %s", key, err)
                    failed += 1
                else:
                    generated += 1
            continue

        # Real generation
        output_dir.mkdir(parents=True, exist_ok=True)
        mp3_path = output_dir / f"{key}.mp3"

        if mp3_path.exists():
            logger.info("  [skip] %s (already exists)", key)
            skipped += 1
            continue

        audio_bytes, err = generate_entry(entry, elevenlabs_svc, dry_run=False)
        if err:
            failed += 1
            continue

        # Write locally
        mp3_path.write_bytes(audio_bytes)
        logger.info("  [generated] %s → %s", key, mp3_path)
        generated += 1

        # Upload if requested
        if args.upload:
            upload_entry(entry, audio_bytes, key)

    print(
        f"\nSummary: {generated} generated, {skipped} skipped, {failed} failed "
        f"out of {len(entries)} entries"
    )


if __name__ == "__main__":
    main()
