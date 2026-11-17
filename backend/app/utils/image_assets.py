"""Shared resolution of catalog names to static image files.

Junk, outfit and pet artwork all follow the same contract: a canonical
lower-cased name maps to a filename in a per-kind static directory, and an
unmapped or missing file resolves to ``None`` so callers can fall back to a
generic icon.
"""

from pathlib import Path


def lookup_image_url(
    name: str | None,
    mapping: dict[str, str],
    image_dir: Path,
    url_prefix: str,
) -> str | None:
    """Return the static image URL for a mapped name, if the file exists.

    The lookup is case-insensitive and ignores leading/trailing whitespace.
    Returns ``None`` when the name is unmapped or the mapped file is missing
    on disk.
    """
    if not name:
        return None

    filename = mapping.get(name.strip().casefold())
    if not filename or not (image_dir / filename).exists():
        return None

    return f"{url_prefix}/{filename}"
