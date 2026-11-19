"""Weapon image URL resolution for backend static assets."""

from functools import cache
from pathlib import Path

from app.utils.weapon_naming import family_key

WEAPON_NAME_TO_IMAGE_FILE = {
    ".32 pistol": "32 pistol FOS.png",
    "10mm pistol": "10mm pistol FOS.png",
    "alien blaster": "Alien Blaster FOS.png",
    "alien disintegrator": "Alien Disintegrator FOS.png",
    "ap .50 cal machine gun": "FOS .50 cal machine gun.png",
    "ap lever-action rifle": "Lever-action rifle fos.png",
    "assault rifle": "Assault Rifle FOS.png",
    "assaultron head": "Assaultron Head FOS.png",
    "baseball bat": "Baseball Bat FOS.png",
    "bb gun": "Bb gun FOS.png",
    "butcher knife": "Butcher Knife FOS.png",
    "combat shotgun": "Double-barrel shotgun FOS.png",
    "fat man": "Fat Man FOS.png",
    "fire hydrant bat": "Fire Hydrant Bat FOS.png",
    "flamer": "Enhanced Flamer Stats FOS.png",
    "gatling laser": "Mean Green Monster FOS.png",
    "gauss pistol": "Gauss Pistol FOS.png",
    "gauss rifle": "Gauss Rifle FOS.png",
    "grognak's axe": "Grognaks Axe FOS.png",
    "henrietta": "Henrietta FOS.png",
    "hunting rifle": "Hunting rifle FOS.png",
    "institute pistol": "Institute Pistol FOS.png",
    "institute rifle": "Institute Rifle FOS.png",
    "junk jet": "Junk Jet FOS.png",
    "kitchen knife": "Kitchen Knife FOS.png",
    "laser musket": "Laser Musket FOS.png",
    "laser pistol": "Laser pistol FOS.png",
    "laser rifle": "Laser Rifle FOS.png",
    "lever-action rifle": "Lever-action rifle fos.png",
    "missile launcher": "Enhanced Missile Launcher Stats FOS.png",
    "pickaxe": "Pickaxe FOS.png",
    "pipe pistol": "Pipe Pistol FOS.png",
    "pipe rifle": "Pipe Rifle FOS.png",
    "plasma pistol": "Plasma Pistol FOS.png",
    "plasma rifle": "Plasma Rifle FOS.png",
    "pool cue": "Pool Cue FOS.png",
    "power fist": "Power Fist FOS.png",
    "pulse rifle": "Pulse Rifle FOS.png",
    "railway rifle": "Railway rifle FOS.png",
    "relentless raider sword": "Relentless Raider Sword FOS.png",
    "ripper": "Ripper FOS.png",
    "rusty pistol": "Rusty .32 Pistol Stats FOS.png",
    "sawed-off shotgun": "Sawed off FOS.png",
    "scoped .44": "Scoped 44 FOS.png",
    "shotgun": "Shotgun FOS.png",
    "sniper rifle": "Hardened Sniper Rifle Stats FOS.png",
}

_WEAPON_IMAGE_DIR = Path(__file__).parent.parent / "static" / "weapon_images"
_FALLBACK_IMAGE_FILE = "10mm pistol FOS.png"


@cache
def _disk_index() -> dict[str, str]:
    """Casefolded filename stem → actual filename for vendored weapon art; built once so
    variant cards resolve by naming convention without growing the hand-authored map.
    """
    return (
        {path.name.casefold(): path.name for path in _WEAPON_IMAGE_DIR.iterdir()} if _WEAPON_IMAGE_DIR.is_dir() else {}
    )


def _convention_lookup(weapon_name: str) -> str | None:
    """Family icon by filename convention (case-insensitive): variants share the family look
    ("Hardened Gauss pistol" → Gauss pistol icon). Only true icons match — stat cards never
    returned.
    """
    index = _disk_index()
    lowered = weapon_name.strip().casefold()
    for candidate in (f"{lowered} fos.png", f"fos {lowered}.png"):
        if candidate in index:
            return index[candidate]
    return None


def get_weapon_image_url(weapon_name: str | None) -> str | None:
    """Exact weapon image when available, else a generic one.

    Resolution order: hand-authored map → family icon by filename convention → family base
    image after stripping the variant prefix → generic 10mm pistol fallback.
    """
    if not weapon_name:
        filename = _FALLBACK_IMAGE_FILE
    else:
        key = weapon_name.strip().casefold()
        filename = WEAPON_NAME_TO_IMAGE_FILE.get(key) or _convention_lookup(key)
        if filename is None:
            family = family_key(key)
            filename = WEAPON_NAME_TO_IMAGE_FILE.get(family) or _convention_lookup(family)
        filename = filename or _FALLBACK_IMAGE_FILE
    return f"/static/weapon_images/{filename}" if (_WEAPON_IMAGE_DIR / filename).exists() else None
