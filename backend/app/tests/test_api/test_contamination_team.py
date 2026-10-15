"""Tests for the contamination team roster endpoint."""

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import HazardTeam
from app.models.incident import IncidentType
from app.models.team import ACTIVE_STATUS, RESERVE_STATUS
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services.exploration.data_loader import load_outfits
from app.services.hazard_team_service import TEAM_SIZE
from app.tests.test_services._hazard_team_helpers import ensure_station, make_member, raise_incident
from app.utils.item_factory import build_outfit


@pytest.mark.asyncio
async def test_roster_reports_every_team(
    async_client: AsyncClient, superuser_token_headers: dict[str, str], vault: Vault
):
    """A vault where nobody has qualified still reports both teams, both empty."""
    response = await async_client.get(
        f"/contamination-team/vault/{vault.id}/roster",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["vault_id"] == str(vault.id)
    assert {team["team"] for team in body["teams"]} == {"fire", "radiation"}
    assert all(team["active"] == [] and team["reserve"] == [] for team in body["teams"])


@pytest.mark.asyncio
async def test_set_place_activates_a_reserve_member(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller_data: dict,
):
    """PUT moves a reserve member to active and returns the updated roster."""
    dweller = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    await ensure_station(async_session, vault.id)
    await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, RESERVE_STATUS)

    response = await async_client.put(
        f"/contamination-team/vault/{vault.id}/fire/{dweller.id}",
        json={"active": True},
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["vault_id"] == str(vault.id)
    fire = next(team for team in body["teams"] if team["team"] == "fire")
    assert [place["dweller_id"] for place in fire["active"]] == [str(dweller.id)]
    assert fire["active"][0]["name"] == dweller.display_name
    assert fire["active"][0]["level"] == dweller.level
    assert fire["reserve"] == []


@pytest.mark.asyncio
async def test_set_place_refused_without_a_response_station(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller_data: dict,
):
    """Promoting a bench member without a station returns the mapped 400 and grants no place."""
    dweller = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, RESERVE_STATUS)

    response = await async_client.put(
        f"/contamination-team/vault/{vault.id}/fire/{dweller.id}",
        json={"active": True},
        headers=superuser_token_headers,
    )

    assert response.status_code == 400
    assert "response station" in response.json()["detail"].lower()
    place = await crud.team_crud.get_hazard_member(async_session, vault.id, HazardTeam.FIRE, dweller.id)
    assert place.status == RESERVE_STATUS


@pytest.mark.asyncio
async def test_set_place_full_team_returns_409(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller_data: dict,
):
    """Activating a fourth member while three hold active places is refused."""
    dwellers = []
    while len(dwellers) <= TEAM_SIZE:
        dwellers.append(
            await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
        )
    await ensure_station(async_session, vault.id)
    for dweller in dwellers[:TEAM_SIZE]:
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)
    await make_member(async_session, vault.id, dwellers[TEAM_SIZE].id, HazardTeam.FIRE, RESERVE_STATUS)

    response = await async_client.put(
        f"/contamination-team/vault/{vault.id}/fire/{dwellers[TEAM_SIZE].id}",
        json={"active": True},
        headers=superuser_token_headers,
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_set_place_without_a_place_returns_404(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller_data: dict,
):
    """A dweller holding no place on the team cannot be moved."""
    dweller = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))

    response = await async_client.put(
        f"/contamination-team/vault/{vault.id}/fire/{dweller.id}",
        json={"active": True},
        headers=superuser_token_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_set_place_requires_vault_ownership(
    async_client: AsyncClient,
    normal_user_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller_data: dict,
):
    """A user who does not own the vault cannot move its team members."""
    dweller = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, RESERVE_STATUS)

    response = await async_client.put(
        f"/contamination-team/vault/{vault.id}/fire/{dweller.id}",
        json={"active": True},
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403


async def _equip_catalog_outfit(async_session: AsyncSession, dweller_id, name: str, storage_id) -> None:
    """Equip a real catalog outfit, built through the factory so catalog-owned columns survive."""
    entry = next(entry for entry in load_outfits() if entry["name"] == name)
    outfit = build_outfit(entry, entry["rarity"], storage_id)
    async_session.add(outfit)
    await async_session.commit()
    await crud.outfit.equip(db_session=async_session, item_id=outfit.id, dweller_id=dweller_id)


@pytest.mark.asyncio
async def test_roster_enrichment_is_identical_across_get_and_put(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    room_with_dwellers: dict,
):
    """GET and a place-changing PUT return the same service counts and current-gear values."""
    room = room_with_dwellers["room"]
    vault_id = room.vault_id
    dweller = room_with_dwellers["dwellers"][0]
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault_id)
    expected_resist = float(
        next(entry for entry in load_outfits() if entry["name"] == "Firefighter suit, rad helmet").get("fire_resist")
        or 0.0
    )
    assert expected_resist > 0.0
    await _equip_catalog_outfit(async_session, dweller.id, "Firefighter suit, rad helmet", storage.id)
    await make_member(async_session, vault_id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)
    for _ in range(2):
        incident = await raise_incident(async_session, room, IncidentType.FIRE)
        await crud.incident_participant_crud.record(async_session, incident.id, [dweller.id])
    await async_session.commit()

    get_response = await async_client.get(
        f"/contamination-team/vault/{vault_id}/roster", headers=superuser_token_headers
    )
    assert get_response.status_code == 200
    before = next(team for team in get_response.json()["teams"] if team["team"] == "fire")["active"][0]
    assert before["service_count"] == 2
    assert before["outfit_name"] == "Firefighter suit, rad helmet"
    assert before["has_matching_gear"] is False
    assert before["hazard_resist"] == pytest.approx(expected_resist)

    put_response = await async_client.put(
        f"/contamination-team/vault/{vault_id}/fire/{dweller.id}",
        json={"active": False},
        headers=superuser_token_headers,
    )
    assert put_response.status_code == 200
    after = next(team for team in put_response.json()["teams"] if team["team"] == "fire")["reserve"][0]
    assert before["status"] == "active"
    assert after["status"] == "reserve"
    enrichment = ("dweller_id", "service_count", "outfit_name", "has_matching_gear", "hazard_resist")
    assert {field: after[field] for field in enrichment} == {field: before[field] for field in enrichment}
