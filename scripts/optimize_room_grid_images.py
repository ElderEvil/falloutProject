"""Rebuild compact room grid artwork: uv run --project backend python scripts/optimize_room_grid_images.py."""

import hashlib
import json
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend/public/assets/room-grid"
MANIFEST = ROOT / "frontend/src/modules/rooms/models/roomGridImages.json"


def main() -> None:
    """Keep detail artwork intact and generate content-addressed WebP grid variants."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sources = [
        *sorted((ROOT / "backend/app/static/room_images").glob("*")),
        *sorted((ROOT / "frontend/public/assets/room-scenes").glob("*.webp")),
    ]
    manifest: dict[str, str] = {}
    original_bytes = compact_bytes = 0
    for source in sources:
        if source.suffix.lower() not in {".png", ".jpg", ".webp"}:
            continue
        with Image.open(source) as image:
            image.thumbnail((768, 256), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            image.save(buffer, format="WEBP", quality=80, method=6)
        content = buffer.getvalue()
        filename = f"{hashlib.sha256(content).hexdigest()[:16]}.webp"
        (OUTPUT / filename).write_bytes(content)
        base = ROOT / (
            "backend/app"
            if source.is_relative_to(ROOT / "backend")
            else "frontend/public"
        )
        manifest[f"/{source.relative_to(base).as_posix()}"] = (
            f"/assets/room-grid/{filename}"
        )
        original_bytes += source.stat().st_size
        compact_bytes += len(content)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    live = {Path(url).name for url in manifest.values()}
    for stale in OUTPUT.glob("*.webp"):
        if stale.name not in live:
            stale.unlink()
    print(f"{len(manifest)} grid images: {original_bytes:,} -> {compact_bytes:,} bytes")


if __name__ == "__main__":
    main()
