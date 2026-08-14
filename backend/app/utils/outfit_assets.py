"""Outfit name to apparel image mapping.

Centralizes the mapping between in-game outfit names and their static image
assets. Unmapped outfits fall back to the generic equipment icon in the UI.
"""

from pathlib import Path

# Maps canonical lower-cased outfit names to the actual filename in
# backend/app/static/apparel_images/. Keep this sorted alphabetically by key.
OUTFIT_NAME_TO_IMAGE_FILE: dict[str, str] = {
    "abraham's relaxedwear": "FOS Formal Wear.png",
    "armored vault suit": "FOS Armored Vault Suit.png",
    "autumn's uniform": "FOS Autumn Uniform.png",
    "bittercup's outfit": "FOS Bittercup Outfit.png",
    "confessor cromwell's rags": "FOS Clergy Outfit.png",
    "elder robe": "FOS Elder Robe.png",
    "eulogy jones' suit": "FOS Eulogy Outfit.png",
    "heavy synth armor": "FOS Combat Armor.png",
    "heavy vault suit": "FOS Armored Vault Suit.png",
    "leather armor": "FOS Leather Armor.png",
    "mechanic jumpsuit": "FOS Handyman Outfit.png",
    "ncr ranger outfit": "FOS Sheriff Duster.png",
    "robco r&d suit": "FOS Labcoat.png",
    "robot armor": "FOS Engineer Armor.png",
    "t-51b power armor": "FOS T51 Outfit.png",
    "vault jumpsuit": "FOS Vault Suit.png",
    "sturdy vault suit": "FOS Vault Suit.png",
    "t-45a power armor": "FOS T45 Outfit.png",
    "t-45d power armor": "FOS T45 Outfit.png",
    "t-45f power armor": "FOS T45 Outfit.png",
    "t-51a power armor": "FOS T51 Outfit.png",
    "t-51d power armor": "FOS T51 Outfit.png",
    "t-51f power armor": "FOS T51 Outfit.png",
    "t-60a power armor": "FOS T60 Outfit.png",
    "t-60d power armor": "FOS T60 Outfit.png",
    "t-60f power armor": "FOS T60 Outfit.png",
    "tattered longcoat": "FOS Sheriff Duster.png",
    "x-01 mk i power armor": "FOS X-01 Outfit.png",
    "x-01 mk iv power armor": "FOS X-01 Outfit.png",
    "x-01 mk vi power armor": "FOS X-01 Outfit.png",
}

_APPAREL_IMAGE_DIR = Path(__file__).parent.parent / "static" / "apparel_images"


def get_outfit_image_url(outfit_name: str | None) -> str | None:
    """Return the static image URL for an outfit, if a mapped asset exists.

    The lookup is case-insensitive and ignores leading/trailing whitespace.
    Returns ``None`` when the outfit is unmapped or the mapped file is missing
    on disk, so callers can fall back to a generic icon.
    """
    if not outfit_name:
        return None

    key = outfit_name.strip().casefold()
    filename = OUTFIT_NAME_TO_IMAGE_FILE.get(key)
    if not filename:
        return None

    if not (_APPAREL_IMAGE_DIR / filename).exists():
        return None

    return f"/static/apparel_images/{filename}"
