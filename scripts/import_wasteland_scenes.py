"""Import a supplied background batch: uv run --project backend python scripts/import_wasteland_scenes.py PATH."""

import argparse
import hashlib
import json
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MAX_VARIANT_BYTES = 200_000
SCENES = {
    "desert_highway": "Desert highway",
    "supermarket_interior": "Abandoned supermarket",
    "subway_station": "Subway station",
    "amusement_park": "Ruined amusement park",
    "arctic_research_station": "Arctic research station",
    "gloomwater_bog": "Gloomwater Bog",
    "gloomwater_bog_night": "Gloomwater Bog at night",
    "outskirts_interchange": "Outskirts interchange",
    "red_rocket": "Red Rocket gas station",
    "raider_tollbooth": "Raider tollbooth",
    "campsite": "Abandoned campsite",
}
SOURCE_NAMES = {
    "gloomwater_bog": "gpt-image-2.5-sunburst-bog.png",
    "gloomwater_bog_night": "gpt-image-2.5-sunburst-bog-night.png",
    "outskirts_interchange": "gpt-image-2.5-sunburst-city-outskirts.png",
    "red_rocket": "gpt-image-2.5-sunburst-red-rocket.png",
    "raider_tollbooth": "gpt-image-2.5-sunburst-kn79va34fvgkf4hmajtr3f9dm98hgvyd.png",
}


def main() -> None:
    """Keep supplied artwork intact and export responsive, content-addressed WebP variants."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument(
        "--only",
        action="append",
        choices=SCENES,
        help="Import only these scenes; existing exports for other scenes are left untouched.",
    )
    args = parser.parse_args()
    source_root = args.source
    scenes = {key: SCENES[key] for key in (args.only or SCENES)}
    output = ROOT / "frontend/public/assets/wasteland-scenes"
    output.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {}
    written: set[str] = set()
    source_bytes = exported_bytes = 0
    for key, label in scenes.items():
        scene: dict[str, object] = {"label": label}
        source = source_root / "Backgrounds" / SOURCE_NAMES.get(key, f"{key}.png")
        data = source.read_bytes()
        source_bytes += len(data)
        variants = []
        with Image.open(source) as original:
            for width in (640, 1280):
                image = original.copy()
                image.thumbnail((width, original.height), Image.Resampling.LANCZOS)
                quality = 80
                buffer = BytesIO()
                image.save(buffer, format="WEBP", quality=quality, method=6)
                content = buffer.getvalue()
                # Keep the committed responsive variants under the test budget.
                while len(content) >= MAX_VARIANT_BYTES and quality > 50:
                    quality -= 5
                    buffer = BytesIO()
                    image.save(buffer, format="WEBP", quality=quality, method=6)
                    content = buffer.getvalue()
                if len(content) >= MAX_VARIANT_BYTES:
                    raise SystemExit(
                        f"{key} at {width}px stays over {MAX_VARIANT_BYTES} bytes at quality 50"
                    )
                digest = hashlib.sha256(content).hexdigest()[:16]
                filename = f"{key.replace('_', '-')}-landscape-{digest}.webp"
                (output / filename).write_bytes(content)
                written.add(filename)
                variants.append(
                    {
                        "src": f"/assets/wasteland-scenes/{filename}",
                        "width": image.width,
                        "height": image.height,
                    }
                )
                exported_bytes += len(content)
        scene["landscape"] = {
            "source": source.relative_to(source_root).as_posix(),
            "source_sha256": hashlib.sha256(data).hexdigest(),
            "variants": variants,
        }
        manifest[key] = scene
    target = ROOT / "frontend/src/modules/exploration/models/wasteland-scenes.json"
    if args.only and target.exists():
        existing: dict[str, object] = json.loads(target.read_text())
        existing.update(manifest)
        manifest = existing
    for stale in output.glob("*.webp"):
        prefix = f"{stale.name.split('-landscape-')[0].replace('-', '_')}-landscape-"
        if prefix in {f"{key.replace('_', '-')}-landscape-" for key in scenes} and stale.name not in written:
            stale.unlink()
    target.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"Imported {len(manifest)} scenes: {source_bytes:,} source bytes -> {exported_bytes:,} WebP bytes"
    )


if __name__ == "__main__":
    main()
