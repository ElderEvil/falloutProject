"""
Utility functions to read application version information.

Reads version from pyproject.toml and provides system info.
"""

import sys
from pathlib import Path

# Python 3.11+ has tomllib built-in, older versions need tomli
try:
    import tomllib
except ImportError:
    import tomli as tomllib


def get_app_version() -> str:
    """
    Read application version from pyproject.toml.

    :returns: Application version string or "unknown" if not found
    :rtype: str
    """
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
            return data["project"]["version"]
    except (FileNotFoundError, KeyError):
        return "unknown"


def get_python_version() -> str:
    """
    Get current Python version.

    :returns: Python version string (e.g., "3.13.1")
    :rtype: str
    """
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def parse_changelog(changelog_path: Path) -> list[dict]:
    """
    Parse CHANGELOG.md and return structured data.

    :param changelog_path: Path to CHANGELOG.md file
    :returns: List of version entries with changes
    """
    import re
    from datetime import datetime

    if not changelog_path.exists():
        return []

    with open(changelog_path, encoding="utf-8") as f:
        content = f.read()

    sections = re.split(r"\n---\n", content)
    versions = []

    for section in sections[1:]:
        lines = section.strip().split("\n")
        if not lines:
            continue

        version_line = lines[0]
        version_match = re.match(r"## \[(\d+\.\d+\.\d+)\] - (\d{4}-\d{2}-\d{2})", version_line)

        if not version_match:
            continue

        version = version_match.group(1)
        date_str = version_match.group(2)

        current_category = None
        changes = []

        for raw_line in lines[1:]:
            line = raw_line.strip()

            if line.startswith("### "):
                current_category = line[4:].strip()
                continue

            if line.startswith("- ") and current_category:
                changes.append({"category": current_category, "description": line[2:].strip()})

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            date_obj = datetime.now()

        versions.append(
            {"version": version, "date": date_obj.isoformat(), "date_display": date_str, "changes": changes}
        )

    return versions


def version_tuple(version_str: str) -> tuple[int, ...]:
    """
    Convert version string to tuple for comparison/sorting.

    :param version_str: Version string (e.g., "2.6.0")
    :returns: Tuple of version components
    """
    parts = version_str.split(".")
    while len(parts) < 3:
        parts.append("0")
    return tuple(map(int, parts[:3]))
