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
