import pytest

from app.core.game_config import game_config
from app.services.changelog_service import changelog_service
from app.utils.version import get_app_version


@pytest.mark.asyncio
class TestChangelogEndpoint:
    async def test_get_changelog_success(self, async_client) -> None:
        response = await async_client.get("/system/changelog")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_latest_changelog_success(self, async_client) -> None:
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

    async def test_get_latest_changelog_empty(self, async_client, monkeypatch) -> None:
        monkeypatch.setattr(changelog_service, "_get_versions", list)
        response = await async_client.get("/system/changelog/latest")
        assert response.status_code == 404
        assert "No changelog entries available" in response.json()["detail"]


@pytest.mark.asyncio
class TestFeaturesEndpoint:
    async def test_get_features_reports_current_switches(self, async_client) -> None:
        response = await async_client.get("/system/features")
        assert response.status_code == 200
        assert response.json() == {
            "race_mechanics": True,
            "faction_mechanics": False,
            "world_events": False,
            "pvp_duels": False,
        }

    async def test_get_features_follows_switch_changes(self, async_client, monkeypatch) -> None:
        monkeypatch.setattr(game_config.features, "faction_mechanics", True)
        response = await async_client.get("/system/features")
        assert response.status_code == 200
        assert response.json()["faction_mechanics"] is True
