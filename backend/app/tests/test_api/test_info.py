"""Tests for system info endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestInfoEndpoint:
    """Test system info endpoint."""

    async def test_get_info_success(self, async_client: AsyncClient) -> None:
        """Test successful info retrieval."""
        response = await async_client.get("/system/info")

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields are present
        assert "app_version" in data
        assert "api_version" in data
        assert "environment" in data
        assert "python_version" in data
        assert "build_date" in data

        # Verify expected values
        assert data["api_version"] == "v1"
        assert data["app_version"] != "unknown"
        assert data["environment"] in ["local", "staging", "production"]

    async def test_get_info_no_auth_required(self, async_client: AsyncClient) -> None:
        """Test info endpoint is public (no auth required)."""
        # Request without Authorization header should succeed
        response = await async_client.get("/system/info")
        assert response.status_code == 200

    async def test_get_info_returns_valid_python_version(self, async_client: AsyncClient) -> None:
        """Test that Python version has valid format."""
        response = await async_client.get("/system/info")
        data = response.json()

        # Python version should be in format X.Y.Z
        python_version = data["python_version"]
        parts = python_version.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)

    async def test_get_info_returns_valid_build_date(self, async_client: AsyncClient) -> None:
        """Test that build_date is a valid ISO format timestamp."""
        response = await async_client.get("/system/info")
        data = response.json()

        # Build date should be ISO format with timezone
        build_date = data["build_date"]
        assert "T" in build_date  # ISO format separator
        assert "+" in build_date or "Z" in build_date  # Has timezone info
