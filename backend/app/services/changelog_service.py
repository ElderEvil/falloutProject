"""Changelog parsing and querying service."""

from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.utils.version import parse_changelog, version_tuple


class ChangelogService:
    """Service for reading and filtering changelog entries."""

    def _get_versions(self) -> list[dict]:
        changelog_path: Path = settings.project_root / "CHANGELOG.md"
        return parse_changelog(changelog_path)

    def get_entries(self, limit: Optional[int] = 10, since: Optional[str] = None) -> list[dict]:
        """Get changelog entries, optionally filtered by version."""
        versions = self._get_versions()

        if since:
            try:
                since_tuple = version_tuple(since)
                versions = [v for v in versions if version_tuple(v["version"]) > since_tuple]
            except (ValueError, AttributeError):
                pass

        versions.sort(key=lambda x: version_tuple(x["version"]), reverse=True)

        if limit:
            versions = versions[:limit]

        return versions

    def get_latest(self) -> dict:
        """Get the latest changelog entry."""
        from app.utils.exceptions import NotFoundException

        versions = self._get_versions()
        if not versions:
            raise NotFoundException(detail="No changelog entries available")

        versions.sort(key=lambda x: version_tuple(x["version"]), reverse=True)
        return versions[0]


changelog_service = ChangelogService()
