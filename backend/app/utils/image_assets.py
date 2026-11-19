"""Shared catalog-name → static-image resolution for junk, outfit and pet art.

Canonical lower-cased name maps to a filename in a per-kind static directory; unmapped
or missing files resolve to None so callers fall back to a generic icon.
"""

from pathlib import Path


def lookup_image_url(
    name: str | None,
    mapping: dict[str, str],
    image_dir: Path,
    url_prefix: str,
) -> str | None:
    """Static image URL for a mapped name if the file exists; case-insensitive,
    whitespace-trimmed. None when unmapped or missing on disk.
    """
    if not name:
        return None

    filename = mapping.get(name.strip().casefold())
    if not filename or not (image_dir / filename).exists():
        return None

    return f"{url_prefix}/{filename}"
