"""Tests for AI Settings admin endpoints (GET/PUT /ai-settings)."""

import pytest

pytestmark = pytest.mark.asyncio


class TestAISettingsEndpoints:
    async def test_get_ai_settings_no_profile(self, async_client, superuser_token_headers) -> None:
        response = await async_client.get("/ai-settings/", headers=superuser_token_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["profile"] is None
        assert "effective" in data
        assert "provider" in data["effective"]
        assert "mode" in data["effective"]

    async def test_get_ai_settings_requires_auth(self, async_client) -> None:
        response = await async_client.get("/ai-settings/")
        assert response.status_code in (401, 403)

    async def test_get_ai_settings_requires_superuser(self, async_client, normal_user_token_headers) -> None:
        response = await async_client.get("/ai-settings/", headers=normal_user_token_headers)
        assert response.status_code == 400

    async def test_put_ai_settings_creates_profile(self, async_client, superuser_token_headers) -> None:
        response = await async_client.put(
            "/ai-settings/",
            headers=superuser_token_headers,
            json={"provider": "lmstudio", "model": "local-model", "base_url": "http://localhost:1234/v1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["profile"] is not None
        assert data["profile"]["provider"] == "lmstudio"
        assert data["profile"]["model"] == "local-model"
        assert data["effective"]["provider"] == "lmstudio"

    async def test_put_ai_settings_updates_profile(self, async_client, superuser_token_headers) -> None:
        await async_client.put(
            "/ai-settings/",
            headers=superuser_token_headers,
            json={"provider": "ollama", "model": "llama2"},
        )
        response = await async_client.put(
            "/ai-settings/",
            headers=superuser_token_headers,
            json={"provider": "lmstudio", "model": "qwen"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["provider"] == "lmstudio"
        assert data["profile"]["model"] == "qwen"

    async def test_put_ai_settings_rejects_invalid_provider(self, async_client, superuser_token_headers) -> None:
        response = await async_client.put(
            "/ai-settings/",
            headers=superuser_token_headers,
            json={"provider": "invalid_provider"},
        )
        assert response.status_code == 400

    async def test_put_ai_settings_requires_superuser(self, async_client, normal_user_token_headers) -> None:
        response = await async_client.put(
            "/ai-settings/",
            headers=normal_user_token_headers,
            json={"provider": "ollama"},
        )
        assert response.status_code == 400

    async def test_put_ai_settings_partial_update(self, async_client, superuser_token_headers) -> None:
        await async_client.put(
            "/ai-settings/",
            headers=superuser_token_headers,
            json={"provider": "ollama", "model": "llama2"},
        )
        response = await async_client.put(
            "/ai-settings/",
            headers=superuser_token_headers,
            json={"model": "mistral"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["provider"] == "ollama"
        assert data["profile"]["model"] == "mistral"

    async def test_get_after_put_returns_stored_profile(self, async_client, superuser_token_headers) -> None:
        await async_client.put(
            "/ai-settings/",
            headers=superuser_token_headers,
            json={"provider": "lmstudio", "model": "test-model", "base_url": "http://x:1234/v1"},
        )
        response = await async_client.get("/ai-settings/", headers=superuser_token_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["provider"] == "lmstudio"
        assert data["profile"]["model"] == "test-model"
        assert data["profile"]["base_url"] == "http://x:1234/v1"
