"""Import a supplied background batch: uv run --project backend python scripts/import_wasteland_scenes.py PATH."""

import argparse
import hashlib
import json
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCENES = {
    "desert_highway": "Desert highway",
    "supermarket_interior": "Abandoned supermarket",
    "subway_station": "Subway station",
    "amusement_park": "Ruined amusement park",
    "arctic_research_station": "Arctic research station",
}


def main() -> None:
    """Keep supplied artwork intact and export responsive, content-addressed WebP variants."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    source_root = parser.parse_args().source
    output = ROOT / "frontend/public/assets/wasteland-scenes"
    output.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {}
    source_bytes = exported_bytes = 0
    for key, label in SCENES.items():
        scene: dict[str, object] = {"label": label}
        for folder, role, widths in [
            ("Backgrounds", "landscape", (640, 1280)),
            ("Battlebacks", "battleback", (500, 1000)),
        ]:
            source = source_root / folder / f"{key}.png"
            data = source.read_bytes()
            source_bytes += len(data)
            variants = []
            with Image.open(source) as original:
                for width in widths:
                    image = original.copy()
                    image.thumbnail((width, original.height), Image.Resampling.LANCZOS)
                    buffer = BytesIO()
                    image.save(buffer, format="WEBP", quality=80, method=6)
                    content = buffer.getvalue()
                    digest = hashlib.sha256(content).hexdigest()[:16]
                    filename = f"{key.replace('_', '-')}-{role}-{digest}.webp"
                    (output / filename).write_bytes(content)
                    variants.append(
                        {
                            "src": f"/assets/wasteland-scenes/{filename}",
                            "width": image.width,
                            "height": image.height,
                        }
                    )
                    exported_bytes += len(content)
            scene[role] = {
                "source": f"{folder}/{source.name}",
                "source_sha256": hashlib.sha256(data).hexdigest(),
                "variants": variants,
            }
        manifest[key] = scene
    target = ROOT / "frontend/src/modules/exploration/models/wasteland-scenes.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"Imported {len(manifest)} scenes: {source_bytes:,} source bytes -> {exported_bytes:,} WebP bytes"
    )


if __name__ == "__main__":
    main()
