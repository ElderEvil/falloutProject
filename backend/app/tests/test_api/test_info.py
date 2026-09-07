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
