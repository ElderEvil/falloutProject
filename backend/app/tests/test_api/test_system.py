"""Tests for system endpoints."""

import pytest
from httpx import AsyncClient


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


@pytest.mark.asyncio
class TestFeaturesEndpoint:
    """Test the feature-switch endpoint."""

    async def test_get_features_reports_current_switches(self, async_client: AsyncClient) -> None:
        """Clients learn both switches; faction ships dark by default."""
        response = await async_client.get("/system/features")

        assert response.status_code == 200
        assert response.json() == {"race_mechanics": True, "faction_mechanics": False}

    async def test_get_features_follows_switch_changes(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Flipping a switch is visible without a restart."""
        from app.core.game_config import game_config

        monkeypatch.setattr(game_config.features, "faction_mechanics", True)
        response = await async_client.get("/system/features")

        assert response.status_code == 200
        assert response.json()["faction_mechanics"] is True
