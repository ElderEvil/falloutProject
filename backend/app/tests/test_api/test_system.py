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
        response = await async_client.get("/system/changelog/latest")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "date" in data
        assert "changes" in data

    async def test_get_latest_changelog_empty(self, async_client: AsyncClient, monkeypatch) -> None:
        """Test latest changelog returns 404 when no entries available."""
        # Mock parse_changelog to return empty list
        from app.api.v1.endpoints import system

        def mock_parse_changelog(_path):
            return []

        monkeypatch.setattr(system, "parse_changelog", mock_parse_changelog)

        response = await async_client.get("/system/changelog/latest")

        assert response.status_code == 404
        data = response.json()
        assert "No changelog entries available" in data["detail"]
