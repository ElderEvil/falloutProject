"""Weapon image URL resolution for backend static assets."""

from pathlib import Path

from app.core.enums import AssetRole
from app.utils.asset_manifest import manifest_url

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

#: Variant prefixes stripped to reach the family base name (FOS naming:
#: "Hardened Gauss pistol" shares the Gauss pistol look). Grounded in the
#: wiki titles harvested for the rare-variant backfill.
_VARIANT_PREFIXES: tuple[str, ...] = (
    "armor piercing",
    "recoil compensated",
    "night-vision",
    "bayoneted",
    "double-barrel",
    "double barrel",
    "hardened",
    "enhanced",
    "focused",
    "amplified",
    "tuned",
    "pressurized",
    "incendiary",
    "improved",
    "excited",
    "scoped",
    "calibrated",
    "tactical",
    "rusty",
    "auto",
    "long",
)

_file_index: dict[str, str] | None = None


def _disk_index() -> dict[str, str]:
    """Casefolded filename stem -> actual filename for vendored weapon art.

    Built once so variant cards resolve by naming convention without growing
    the hand-authored map per entry.
    """
    global _file_index
    if _file_index is None:
        _file_index = (
            {path.name.casefold(): path.name for path in _WEAPON_IMAGE_DIR.iterdir()}
            if _WEAPON_IMAGE_DIR.is_dir()
            else {}
        )
    return _file_index


def _family_key(weapon_name: str) -> str:
    lowered = weapon_name.strip().casefold()
    for prefix in _VARIANT_PREFIXES:
        if lowered.startswith(prefix + " "):
            return lowered[len(prefix) + 1 :]
    return lowered


def _convention_lookup(weapon_name: str) -> str | None:
    """Family icon by filename convention (case-insensitive).

    Variants share their family look: "Hardened Gauss pistol" resolves to the
    Gauss pistol icon. Only true icons match — stat cards are never returned.
    """
    index = _disk_index()
    lowered = weapon_name.strip().casefold()
    for candidate in (f"{lowered} fos.png", f"fos {lowered}.png"):
        if candidate in index:
            return index[candidate]
    return None


def get_weapon_image_url(weapon_name: str | None) -> str | None:
    """Return an exact weapon image when available, otherwise a generic weapon image.

    Resolution order: hand-authored map, family icon by filename convention
    (variants share the family look), family base image after stripping the
    variant prefix, then the generic 10mm pistol fallback.
    """
    if weapon_name and (url := manifest_url(AssetRole.WEAPON_ICON, weapon_name)):
        return url

    if not weapon_name:
        filename = _FALLBACK_IMAGE_FILE
    else:
        key = weapon_name.strip().casefold()
        filename = WEAPON_NAME_TO_IMAGE_FILE.get(key) or _convention_lookup(key)
        if filename is None:
            family = _family_key(key)
            filename = WEAPON_NAME_TO_IMAGE_FILE.get(family) or _convention_lookup(family)
        filename = filename or _FALLBACK_IMAGE_FILE
    return f"/static/weapon_images/{filename}" if (_WEAPON_IMAGE_DIR / filename).exists() else None
