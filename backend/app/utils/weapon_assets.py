"""Weapon image URL resolution for backend static assets."""

from pathlib import Path

WEAPON_NAME_TO_IMAGE_FILE = {
    ".32 pistol": "32 pistol FOS.png",
    "10mm pistol": "10mm pistol FOS.png",
    "bb gun": "Bb gun FOS.png",
    "combat shotgun": "Double-barrel shotgun FOS.png",
    "fat man": "Fat Man FOS.png",
    "flamer": "Enhanced Flamer Stats FOS.png",
    "gatling laser": "Mean Green Monster FOS.png",
    "hunting rifle": "Hunting rifle FOS.png",
    "laser pistol": "Laser pistol FOS.png",
    "lever-action rifle": "Lever-action rifle fos.png",
    "missile launcher": "Enhanced Missile Launcher Stats FOS.png",
    "railway rifle": "Railway rifle FOS.png",
    "rusty pistol": "Rusty .32 Pistol Stats FOS.png",
    "sawed-off shotgun": "Sawed off FOS.png",
    "scoped .44": "Scoped 44 FOS.png",
    "sniper rifle": "Hardened Sniper Rifle Stats FOS.png",
}

_WEAPON_IMAGE_DIR = Path(__file__).parent.parent / "static" / "weapon_images"
_FALLBACK_IMAGE_FILE = "10mm pistol FOS.png"


def get_weapon_image_url(weapon_name: str | None) -> str | None:
    """Return an exact weapon image when available, otherwise a generic weapon image."""
    filename = WEAPON_NAME_TO_IMAGE_FILE.get(weapon_name.strip().casefold()) if weapon_name else _FALLBACK_IMAGE_FILE
    filename = filename or _FALLBACK_IMAGE_FILE
    return f"/static/weapon_images/{filename}" if (_WEAPON_IMAGE_DIR / filename).exists() else None
