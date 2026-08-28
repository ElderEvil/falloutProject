"""Tests for system endpoints."""

import json
from pathlib import Path

import pytest
from httpx import AsyncClient

PROJECT_ROOT = Path(__file__).parents[4]


def test_changelog_and_release_config_are_link_free() -> None:
    """Release notes stay readable plain text, including future generated entries."""
    changelog = (PROJECT_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    release_config = json.loads((PROJECT_ROOT / ".releaserc.json").read_text(encoding="utf-8"))
    generator = next(
        config for config in release_config["plugins"] if config[0] == "@semantic-release/release-notes-generator"
    )[1]

    assert "](" not in changelog
    assert generator["linkCompare"] is False
    assert generator["linkReferences"] is False


@pytest.mark.asyncio
class TestChangelogEndpoint:
    """Test changelog endpoints."""

    async def test_get_changelog_success(self, async_client: AsyncClient) -> None:
        """Test successful changelog retrieval."""
        response = await async_client.get("/system/changelog")

        assert response.status_code == 200
        data = response.json()

        # Should return a list
        assert isinstance(data, list)

    async def test_get_latest_changelog_success(self, async_client: AsyncClient) -> None:
        """Test successful latest changelog retrieval."""
        from app.utils.version import get_app_version

        response = await async_client.get("/system/changelog/latest")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "date" in data
        assert "changes" in data

        # The latest changelog entry MUST match the current app version
        assert data["version"] == get_app_version(), (
            f"Latest changelog version {data['version']!r} does not match get_app_version(). "
            "CHANGELOG.md must be updated when the app version bumps."
        )
        assert isinstance(data["changes"], list), "changes must be a list"

    async def test_get_changelog_latest_matches_app_version(self) -> None:
        """Test invariant: latest changelog entry version == app version.

        This test runs WITHOUT an HTTP client — it directly invokes the
        changelog service and version utility.  It locks the invariant that
        the API can never serve a changelog older than the running app.
        """
        from app.services.changelog_service import changelog_service
        from app.utils.version import get_app_version

        latest = changelog_service.get_latest()
        app_version = get_app_version()

        assert latest["version"] == app_version, (
            f"Changelog latest version {latest['version']!r} != app version {app_version!r}. "
            "CHANGELOG.md must be updated when pyproject.toml version bumps."
        )

    async def test_get_latest_changelog_empty(self, async_client: AsyncClient, monkeypatch) -> None:
        """Test latest changelog returns 404 when no entries available."""
        from app.services.changelog_service import changelog_service

        def mock_empty():
            return []

        monkeypatch.setattr(changelog_service, "_get_versions", mock_empty)

        response = await async_client.get("/system/changelog/latest")

        assert response.status_code == 404
        data = response.json()
        assert "No changelog entries available" in data["detail"]
