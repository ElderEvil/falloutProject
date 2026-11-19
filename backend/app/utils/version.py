"""Read application version information from pyproject.toml and provide system info."""

import sys
import tomllib
from pathlib import Path


def get_app_version() -> str:
    """Read application version from pyproject.toml, or "unknown" if not found."""
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"

    try:
        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)
            return data["project"]["version"]
    except FileNotFoundError, KeyError:
        return "unknown"


def get_python_version() -> str:
    """Get current Python version."""
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def parse_changelog(changelog_path: Path) -> list[dict]:
    """Parse CHANGELOG.md into structured version entries."""
    import re
    from datetime import datetime

    from app.utils.time import utcnow

    if not changelog_path.exists():
        return []

    with changelog_path.open(encoding="utf-8") as f:
        content = f.read()

    versions = []
    heading_pattern = re.compile(
        r"^## (?:\[)?(?P<version>\d+\.\d+\.\d+)(?:\])?(?:\([^\n)]*\))?(?:\s+-\s+|\s+\()(?P<date>\d{4}-\d{2}-\d{2})\)?\s*$",
        re.MULTILINE,
    )
    headings = list(heading_pattern.finditer(content))

    for index, heading in enumerate(headings):
        version = heading.group("version")
        date_str = heading.group("date")
        section_end = headings[index + 1].start() if index + 1 < len(headings) else len(content)
        lines = content[heading.end() : section_end].split("\n")

        current_category = None
        changes = []

        for raw_line in lines[1:]:
            line = raw_line.strip()

            if line.startswith("### "):
                current_category = line[4:].strip()
                continue

            if line.startswith(("- ", "* ")) and current_category:
                changes.append({"category": current_category, "description": line[2:].strip()})

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            date_obj = utcnow()

        versions.append(
            {"version": version, "date": date_obj.isoformat(), "date_display": date_str, "changes": changes}
        )

    return versions


def version_tuple(version_str: str) -> tuple[int, ...]:
    """Convert a version string to a tuple for comparison/sorting."""
    parts = version_str.split(".")
    while len(parts) < 3:
        parts.append("0")
    return tuple(map(int, parts[:3]))
