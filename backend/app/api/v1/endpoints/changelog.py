"""System endpoint for changelog information."""

import re
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


def parse_changelog() -> list[dict[str, Any]]:
    """Parse CHANGELOG.md and return structured data."""
    changelog_path = settings.project_root / "CHANGELOG.md"

    if not changelog_path.exists():
        return []

    with open(changelog_path, encoding="utf-8") as f:
        content = f.read()

    # Split into version sections
    sections = re.split(r"\n---\n", content)
    versions = []

    for section in sections[1:]:  # Skip header section
        lines = section.strip().split("\n")
        if not lines:
            continue

        # Extract version info from first line
        version_line = lines[0]
        version_match = re.match(r"## \[(\d+\.\d+\.\d+)\] - (\d{4}-\d{2}-\d{2})", version_line)

        if not version_match:
            continue

        version = version_match.group(1)
        date_str = version_match.group(2)

        # Parse the rest of the section
        current_category = None
        changes = []

        for raw_line in lines[1:]:
            line = raw_line.strip()

            # Category headers
            if line.startswith("### "):
                current_category = line[4:].strip()
                continue

            # Change items
            if line.startswith("- ") and current_category:
                changes.append({"category": current_category, "description": line[2:].strip()})

        # Convert date string to datetime
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            date_obj = datetime.now()

        versions.append(
            {"version": version, "date": date_obj.isoformat(), "date_display": date_str, "changes": changes}
        )

    return versions


@router.get("/", response_model=list[dict[str, Any]])
async def get_changelog(limit: Optional[int] = 10, since: Optional[str] = None):
    """
    Get changelog entries.

    Args:
        limit: Maximum number of versions to return (default: 10)
        since: Return versions since this version (e.g., "2.6.0")
    """
    versions = parse_changelog()

    # Filter by version if 'since' is provided
    if since:
        try:
            since_major, since_minor, since_patch = map(int, since.split("."))
            versions = [
                v
                for v in versions
                if tuple(map(int, v["version"].split("."))) > (since_major, since_minor, since_patch)
            ]
        except (ValueError, AttributeError):
            pass

    # Sort by version (newest first) and apply limit
    def version_tuple(version_str):
        parts = version_str.split(".")
        # Ensure we always have 3 parts (pad with zeros if needed)
        while len(parts) < 3:
            parts.append("0")
        return tuple(map(int, parts[:3]))

    versions.sort(key=lambda x: version_tuple(x["version"]), reverse=True)

    if limit:
        versions = versions[:limit]

    return versions


@router.get("/latest", response_model=dict[str, Any])
async def get_latest_changelog():
    """Get the latest changelog entry."""
    versions = parse_changelog()

    if not versions:
        return {}

    # Sort and return the latest version
    versions.sort(key=lambda x: tuple(map(int, x["version"].split("."))), reverse=True)
    return versions[0]
