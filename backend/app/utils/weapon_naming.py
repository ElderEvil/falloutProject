"""Catalog variant names shared by item art and storage maintenance."""

VARIANT_PREFIXES: tuple[str, ...] = (
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
    "ap",
    "auto",
    "long",
)


def family_key(name: str) -> str:
    """Strip the longest recognized variant prefix from a normalized name."""
    name = name.strip().casefold()
    for prefix in sorted(VARIANT_PREFIXES, key=len, reverse=True):
        if name.startswith(prefix + " "):
            return name[len(prefix) + 1 :]
    return name
