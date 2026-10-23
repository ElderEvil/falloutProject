"""Pagination bounds and existing flat query contracts across list routes."""

from datetime import datetime, timedelta

import pytest

from app import crud
from app.core.config import settings
from app.models.chat_message import ChatMessage
from app.schemas.dweller import DwellerCreate
from app.tests.factory.dwellers import create_fake_adult_dweller
from main import app

LIST_PATHS = [
    "/users/",
    "/vaults/",
    "/rooms/",
    "/rooms/vault/{vault_id}/",
    "/dwellers/",
    "/dwellers/vault/{vault_id}/",
    "/dwellers/vault/{vault_id}/dead",
    "/dwellers/vault/{vault_id}/graveyard",
    "/dwellers/vault/{vault_id}/deleted",
    "/quests/",
    "/quests/{vault_id}/",
    "/quests/{vault_id}/available",
    "/objectives/{vault_id}/",
    "/weapons/",
    "/outfits/",
    "/junk/",
    "/pets/",
    "/chat/history/{dweller_id}",
    "/notifications/",
]


@pytest.mark.parametrize("path", LIST_PATHS)
@pytest.mark.parametrize("limit", [0, -1, 1001])
async def test_list_routes_reject_out_of_bounds_limit(
    async_client, superuser_token_headers, vault, dweller, path, limit
):
    response = await async_client.get(
        path.format(vault_id=vault.id, dweller_id=dweller.id),
        params={"vault_id": str(vault.id), "limit": limit},
        headers=superuser_token_headers,
    )
    assert response.status_code == 422, response.text
    assert any(error["loc"] == ["query", "limit"] for error in response.json()["detail"])


@pytest.mark.parametrize("path", LIST_PATHS)
async def test_list_routes_reject_negative_position(async_client, superuser_token_headers, vault, dweller, path):
    position = "offset" if path.startswith(("/chat/", "/notifications/")) else "skip"
    response = await async_client.get(
        path.format(vault_id=vault.id, dweller_id=dweller.id),
        params={"vault_id": str(vault.id), position: -1},
        headers=superuser_token_headers,
    )
    assert response.status_code == 422, response.text
    assert any(error["loc"] == ["query", position] for error in response.json()["detail"])


@pytest.mark.parametrize("path", LIST_PATHS)
def test_openapi_keeps_flat_pagination_and_defaults(path):
    parameters = app.openapi()["paths"][f"{settings.API_V1_STR}{path}"]["get"]["parameters"]
    query = {parameter["name"]: parameter for parameter in parameters if parameter["in"] == "query"}
    position = "offset" if path.startswith(("/chat/", "/notifications/")) else "skip"
    assert query[position]["schema"]["default"] == 0
    assert query[position]["schema"]["minimum"] == 0
    assert query["limit"]["schema"]["default"] == (50 if path == "/notifications/" else 100)
    assert query["limit"]["schema"]["minimum"] == 1
    assert query["limit"]["schema"]["maximum"] == (100 if path == "/pets/" else 1000)
    assert not query["limit"]["required"]


async def test_roster_accepts_complete_fetch_with_existing_filters(
    async_client, superuser_token_headers, vault, dweller
):
    response = await async_client.get(
        f"/dwellers/vault/{vault.id}/",
        params={"limit": 1000, "search": dweller.first_name, "sort_by": "name", "order": "asc"},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200, response.text
    assert [entry["id"] for entry in response.json()] == [str(dweller.id)]


async def test_roster_applies_filter_and_sort_before_skip(
    async_client, async_session, superuser_token_headers, vault, dweller
):
    dweller.first_name = "Pagination Alpha"
    await async_session.commit()
    other = await crud.dweller.create(
        async_session,
        DwellerCreate(**(create_fake_adult_dweller() | {"first_name": "Pagination Beta", "vault_id": vault.id})),
    )
    response = await async_client.get(
        f"/dwellers/vault/{vault.id}/",
        params={"search": "Pagination", "sort_by": "name", "order": "asc", "skip": 1, "limit": 1},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200, response.text
    assert [entry["id"] for entry in response.json()] == [str(other.id)]


async def test_chat_preserves_offset_pagination(
    async_client, async_session, superuser_token_headers, superuser, vault, dweller
):
    for index in range(3):
        async_session.add(
            ChatMessage(
                vault_id=vault.id,
                from_user_id=superuser.id,
                to_dweller_id=dweller.id,
                message_text=f"Message {index}",
                created_at=datetime(2026, 1, 1) + timedelta(seconds=index),
            )
        )
    await async_session.commit()
    response = await async_client.get(
        f"/chat/history/{dweller.id}", params={"offset": 1, "limit": 1}, headers=superuser_token_headers
    )
    assert response.status_code == 200, response.text
    assert [entry["message_text"] for entry in response.json()] == ["Message 1"]


@pytest.mark.parametrize("limit", [0, -1, 1001])
async def test_changelog_limit_is_bounded(async_client, limit):
    response = await async_client.get("/system/changelog", params={"limit": limit})
    assert response.status_code == 422
