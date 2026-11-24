import pytest

from app.core.enums import DwellerLocationRelationEnum, LocationTypeEnum
from app.core.game_config import game_config
from app.crud.vault_slot import vault_slot
from app.crud.world_location import world_location as wl_crud
from app.services.collectible_service import collectible_service
from app.services.dweller_service import dweller_service
from app.services.map_service import map_service
from app.services.world_snapshot_service import world_snapshot_service


async def test_get_vault_map_includes_bio_places(
    async_client, async_session, superuser_token_headers, vault, dweller
) -> None:
    await map_service.register_bio_places(
        async_session, dweller, origin_place="Megaton", visited_places=["Rivet City", "Tenpenny Tower"]
    )
    # Second dweller also from Megaton (use create_random for full defaults)
    dw2 = await dweller_service.create_random_dweller(async_session, vault.id)
    await map_service.register_bio_places(async_session, dw2, origin_place="Megaton", visited_places=["Tenpenny Tower"])

    response = await async_client.get(f"/map/vault/{vault.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    locations_with_dwellers = [loc for loc in data["locations"] if loc["dwellers"]]
    assert len(locations_with_dwellers) >= 1
    first_dwellers = locations_with_dwellers[0]["dwellers"]
    assert len(first_dwellers) >= 1
    ref = first_dwellers[0]
    assert "dweller_id" in ref
    assert "first_name" in ref
    assert "relation" in ref
    # The group taxonomy rides along: the catalog ships and known names resolve.
    assert data["place_groups"], "map payload carries the group catalog"
    assert "settlement" in {group["key"] for group in data["place_groups"]}
    megaton = next(loc for loc in data["locations"] if loc["name"] == "Megaton")
    assert megaton["group_key"] == "settlement"


async def test_get_vault_map_includes_discoverable_player_vaults(
    async_client, async_session, superuser_token_headers, vault
) -> None:
    await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
    await async_session.commit()
    response = await async_client.get(f"/map/vault/{vault.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    player_vaults = response.json()["player_vaults"]
    mine = next((pv for pv in player_vaults if pv["vault_id"] == str(vault.id)), None)
    assert mine is not None
    assert mine["number"] == vault.number
    assert mine["is_mine"] is True
    assert all(0 < pv["coord_x"] < 160 and 0 < pv["coord_y"] < 160 for pv in player_vaults)


async def test_get_location_detail_with_dwellers(
    async_client, async_session, superuser_token_headers, vault, dweller
) -> None:
    await map_service.register_bio_places(async_session, dweller, origin_place="Rivet City", visited_places=[])
    loc = await wl_crud.get_registry_by_normalized(async_session, "rivet city")
    assert loc is not None
    response = await async_client.get(f"/map/vault/{vault.id}/locations/{loc.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(loc.id)
    assert data["type"] == LocationTypeEnum.ORIGIN
    assert len(data["dwellers"]) >= 1
    ref = data["dwellers"][0]
    assert ref["dweller_id"] == str(dweller.id)
    assert ref["first_name"] == dweller.first_name
    assert ref["relation"] == DwellerLocationRelationEnum.ORIGIN


async def test_world_roads_api_is_authenticated_and_reads_the_persisted_layer(
    async_client, async_session, superuser_token_headers
) -> None:
    assert (await async_client.get("/map/world")).status_code == 401
    snapshot = await world_snapshot_service.get_or_generate(async_session)
    response = await async_client.get("/map/world", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["roads"] == snapshot.roads
    assert data["terrain"] == snapshot.terrain
    assert data["roads"]["base_checksum"] == data["snapshot_checksum"]
    assert set(data["roads"]) == {"version", "base_checksum", "checksum", "segments"}
    snapshot.roads = None
    await async_session.commit()
    response = await async_client.get("/map/world", headers=superuser_token_headers)
    assert response.json()["roads"] is None
    await async_session.refresh(snapshot)
    assert snapshot.roads is None  # reads do not backfill


async def test_get_vault_map_reports_collectible_set_progress(
    async_client, async_session, superuser_token_headers, vault, dweller, monkeypatch
) -> None:
    monkeypatch.setattr(game_config.features, "collectibles", True)
    for key in ("grognak_barbarian", "astounding_tales"):
        assert await collectible_service.award(async_session, vault_id=vault.id, dweller=dweller, collectible_key=key)
    await async_session.commit()
    response = await async_client.get(f"/map/vault/{vault.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    progress = {row["set"]: row for row in response.json()["collectible_sets"]}
    assert progress["comics"] == {"set": "comics", "name": "The Full Run", "held": 2, "required": 3, "active": False}
    assert progress["bobbleheads"] == {
        "set": "bobbleheads",
        "name": "Full Cabinet",
        "held": 0,
        "required": 7,
        "active": False,
    }
