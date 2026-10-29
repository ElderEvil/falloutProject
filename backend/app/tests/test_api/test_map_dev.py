"""Dev-only map lab endpoint: ephemeral v3 worlds for the local inspector."""

import pytest
from httpx import AsyncClient

from app.core.config import settings

pytestmark = pytest.mark.asyncio


async def test_preview_world_returns_a_full_v3_payload(async_client: AsyncClient) -> None:
    response = await async_client.get("/map/dev/world", params={"seed": "lab-seed"})

    assert response.status_code == 200
    body = response.json()
    assert body["generator_version"] == 3
    assert len(body["regions"]) == 4
    assert len(body["region_map"]) == body["width"] * body["height"]
    assert body["roads"]
    assert body["rivers"] == []
    assert body["road_edges"]
    assert len(body["slots"]) == 100
    assert body["validation"]["reachable_slot_tiles"] == 100
    assert body["validation"]["roads"]["slots_with_road"] == 100


async def test_preview_world_is_deterministic_per_seed(async_client: AsyncClient) -> None:
    first = (await async_client.get("/map/dev/world", params={"seed": "same-seed"})).json()
    second = (await async_client.get("/map/dev/world", params={"seed": "same-seed"})).json()
    other = (await async_client.get("/map/dev/world", params={"seed": "other-seed"})).json()

    assert first["recipe_fingerprint"] == second["recipe_fingerprint"]
    assert first["terrain"] == second["terrain"]
    assert first["region_map"] == second["region_map"]
    assert first["recipe_fingerprint"] != other["recipe_fingerprint"]
    assert first["terrain"] != other["terrain"]


async def test_preview_world_is_unavailable_outside_local(
    async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    response = await async_client.get("/map/dev/world", params={"seed": "lab-seed"})

    assert response.status_code == 404
