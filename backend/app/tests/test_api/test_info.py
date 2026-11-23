import pytest


@pytest.mark.asyncio
class TestInfoEndpoint:
    async def test_get_info_success(self, async_client) -> None:
        response = await async_client.get("/system/info")

        assert response.status_code == 200
        data = response.json()
        assert "app_version" in data
        assert "api_version" in data
        assert "environment" in data
        assert "python_version" in data
        assert "build_date" in data
        assert data["api_version"] == "v1"
        assert data["app_version"] != "unknown"
        assert data["environment"] in ["local", "staging", "production"]
