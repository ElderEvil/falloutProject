"""Junk name to crafting-component image mapping.

Every junk catalog entry resolves to its FOS icon (a few only exist as cards).
Duct tape shares the military duct tape art — the wiki carries no separate icon.
Unmapped junk falls back to the generic icon in the UI.
"""

from pathlib import Path

# Maps canonical lower-cased junk names to the actual filename in
# backend/app/static/junk_images/. Keep this sorted alphabetically by key.
JUNK_NAME_TO_IMAGE_FILE: dict[str, str] = {
    "alarm clock": "FOS Alarm clock.png",
    "baseball glove": "FOS Baseball glove.png",
    "brahmin hide": "FOS Brahmin hide.png",
    "camera": "FOS Camera.png",
    "chemistry flask": "FOS Chemistry flask.png",
    "desk fan": "FOS Desk fan.png",
    "duct tape": "FOS Military duct tape.png",
    "giddyup buttercup": "FOS Giddyup Buttercup.png",
    "globe": "FOS Globe.png",
    "gold watch": "FOS Gold watch.png",
    "magnifying glass": "FOS Magnifying glass.png",
    "microscope": "FOS Microscope.png",
    "military circuit board": "FOS Military circuit board.png",
    "military duct tape": "FOS Military duct tape.png",
    "shovel": "FOS Shovel.png",
    "teddy bear": "FOS Teddy bear.png",
    "toy car": "FOS Toy car.png",
    "tri-fold flag": "FOS Tri-fold flag.png",
    "wonderglue": "FOS Wonderglue.png",
    "yao guai hide": "FOS Yao guai hide.png",
    "yarn": "FOS Yarn.png",
}

_JUNK_IMAGE_DIR = Path(__file__).parent.parent / "static" / "junk_images"


def get_junk_image_url(junk_name: str | None) -> str | None:
    """Return the static image URL for a junk item, if a mapped asset exists.

    The lookup is case-insensitive and ignores leading/trailing whitespace.
    Returns ``None`` when the junk is unmapped or the mapped file is missing
    on disk, so callers can fall back to a generic icon.
    """
    if not junk_name:
        return None

    key = junk_name.strip().casefold()
    filename = JUNK_NAME_TO_IMAGE_FILE.get(key)
    if not filename:
        return None

    if not (_JUNK_IMAGE_DIR / filename).exists():
        return None

    return f"/static/junk_images/{filename}"
