from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.v1.endpoints.dweller import extend_bio
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum
from app.schemas.dweller import DwellerCreate
from app.tests.factory.dwellers import create_fake_dweller


async def test_extend_bio_endpoint_delegates_to_ai_service() -> None:
    user = MagicMock()
    session = MagicMock()
    dweller_id = uuid4()
    expected = MagicMock()

    with patch("app.api.v1.endpoints.dweller.dweller_ai.extend_bio", new=AsyncMock(return_value=expected)) as extend:
        result = await extend_bio(dweller_id=dweller_id, user=user, db_session=session)

    assert result is expected
    extend.assert_awaited_once_with(db_session=session, dweller_id=dweller_id, user=user)


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_create_dweller(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    room: Room,
    dweller_data: dict,
) -> None:
    dweller_data.update({"vault_id": str(room.vault_id), "room_id": str(room.id)})
    response = await async_client.post("/dwellers/", json=dweller_data, headers=superuser_token_headers)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["first_name"] == dweller_data["first_name"]
    assert response_data["last_name"] == dweller_data["last_name"]
    assert response_data["is_adult"] == dweller_data["is_adult"]
    assert response_data["gender"] == dweller_data["gender"]
    assert response_data["rarity"] == dweller_data["rarity"]
    assert response_data["level"] == dweller_data["level"]
    assert response_data["experience"] == dweller_data["experience"]
    assert response_data["max_health"] == dweller_data["max_health"]
    assert response_data["health"] == dweller_data["health"]
    assert response_data["radiation"] == dweller_data["radiation"]
    assert response_data["happiness"] == dweller_data["happiness"]
    assert response_data["stimpack"] == dweller_data["stimpack"]
    assert response_data["radaway"] == dweller_data["radaway"]
    assert "status" in response_data


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_read_dweller_list_exposes_weapon_type(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    equipped_dweller: tuple[Dweller, object, object],
) -> None:
    """DwellerReadLess must serialize weapon_type without lazy-loading (MissingGreenlet guard)."""
    dweller, _, weapon = equipped_dweller
    response = await async_client.get("/dwellers/", headers=superuser_token_headers)
    assert response.status_code == 200
    by_id = {d["id"]: d for d in response.json()}
    assert by_id[str(dweller.id)]["weapon_type"] == weapon.weapon_type.value


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_delete_dweller(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    dweller: Dweller,
) -> None:
    delete_response = await async_client.delete(f"/dwellers/{dweller.id}", headers=superuser_token_headers)
    assert delete_response.status_code == 204
    read_response = await async_client.get(f"/dwellers/{dweller.id}", headers=superuser_token_headers)
    assert read_response.status_code == 404


@pytest.mark.asyncio
async def test_filter_dwellers_by_status(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    room: Room,
) -> None:
    """Test filtering dwellers by status."""
    from app.schemas.common import DwellerStatusEnum
    from app.schemas.dweller import DwellerUpdate

    # Create dwellers with different statuses
    dweller_1_data = create_fake_dweller()
    dweller_2_data = create_fake_dweller()
    dweller_1_data.update({"vault_id": str(room.vault_id), "room_id": str(room.id)})
    dweller_2_data.update({"vault_id": str(room.vault_id)})

    dweller_1_in = DwellerCreate(**dweller_1_data)
    dweller_2_in = DwellerCreate(**dweller_2_data)

    dweller_1 = await crud.dweller.create(async_session, dweller_1_in)
    dweller_2 = await crud.dweller.create(async_session, dweller_2_in)

    # Update dweller_1 to WORKING status
    await crud.dweller.update(async_session, dweller_1.id, DwellerUpdate(status=DwellerStatusEnum.WORKING))
    # dweller_2 stays IDLE

    # Filter by WORKING status
    response = await async_client.get(
        f"/dwellers/vault/{room.vault_id}/?status=working", headers=superuser_token_headers
    )
    assert response.status_code == 200
    dwellers = response.json()
    assert len(dwellers) == 1
    assert dwellers[0]["status"] == "working"

    # Filter by IDLE status
    response = await async_client.get(f"/dwellers/vault/{room.vault_id}/?status=idle", headers=superuser_token_headers)
    assert response.status_code == 200
    dwellers = response.json()
    assert len(dwellers) == 1
    assert dwellers[0]["status"] == "idle"


@pytest.mark.asyncio
async def test_search_dwellers_by_name(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    room: Room,
) -> None:
    """Test searching dwellers by name."""

    # Create dwellers with specific names
    dweller_1_data = create_fake_dweller()
    dweller_2_data = create_fake_dweller()
    dweller_1_data.update(
        {
            "first_name": "John",
            "last_name": "Smith",
            "vault_id": str(room.vault_id),
        }
    )
    dweller_2_data.update(
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "vault_id": str(room.vault_id),
        }
    )

    dweller_1_in = DwellerCreate(**dweller_1_data)
    dweller_2_in = DwellerCreate(**dweller_2_data)

    await crud.dweller.create(async_session, dweller_1_in)
    await crud.dweller.create(async_session, dweller_2_in)

    # Search by first name
    response = await async_client.get(f"/dwellers/vault/{room.vault_id}/?search=John", headers=superuser_token_headers)
    assert response.status_code == 200
    dwellers = response.json()
    assert len(dwellers) == 1
    assert dwellers[0]["first_name"] == "John"

    # Search by last name (case insensitive)
    response = await async_client.get(f"/dwellers/vault/{room.vault_id}/?search=doe", headers=superuser_token_headers)
    assert response.status_code == 200
    dwellers = response.json()
    assert len(dwellers) == 1
    assert dwellers[0]["last_name"] == "Doe"


@pytest.mark.asyncio
async def test_sort_dwellers(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    room: Room,
) -> None:
    """Test sorting dwellers."""

    # Create dwellers with different levels
    dweller_1_data = create_fake_dweller()
    dweller_2_data = create_fake_dweller()
    dweller_1_data.update({"level": 5, "vault_id": str(room.vault_id)})
    dweller_2_data.update({"level": 10, "vault_id": str(room.vault_id)})

    dweller_1_in = DwellerCreate(**dweller_1_data)
    dweller_2_in = DwellerCreate(**dweller_2_data)

    await crud.dweller.create(async_session, dweller_1_in)
    await crud.dweller.create(async_session, dweller_2_in)

    # Sort by level ascending
    response = await async_client.get(
        f"/dwellers/vault/{room.vault_id}/?sort_by=level&order=asc", headers=superuser_token_headers
    )
    assert response.status_code == 200
    dwellers = response.json()
    assert len(dwellers) == 2
    assert dwellers[0]["level"] == 5
    assert dwellers[1]["level"] == 10

    # Sort by level descending
    response = await async_client.get(
        f"/dwellers/vault/{room.vault_id}/?sort_by=level&order=desc", headers=superuser_token_headers
    )
    assert response.status_code == 200
    dwellers = response.json()
    assert len(dwellers) == 2
    assert dwellers[0]["level"] == 10
    assert dwellers[1]["level"] == 5


@pytest.mark.asyncio
async def test_read_dweller_lineage_not_found(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """GET /dwellers/{id}/lineage returns 404 for a non-existent dweller."""
    response = await async_client.get(f"/dwellers/{uuid4()}/lineage", headers=superuser_token_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_add_bio_addendum_records_dialogue_entry(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    room: Room,
    dweller_data: dict,
) -> None:
    """A confirmed conversation detail lands as a dialogue entry and recompiles the bio."""
    dweller_data.update({"vault_id": str(room.vault_id)})
    dweller = await crud.dweller.create(async_session, DwellerCreate(**dweller_data))

    response = await async_client.post(
        f"/dwellers/{dweller.id}/bio/addendum/",
        json={"text": "I keep a lucky wrench under my bunk."},
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    body = response.json()
    entries = body["bio_entries"]
    assert any(entry["source"] == "dialogue" and "lucky wrench" in entry["text"] for entry in entries)
    assert "lucky wrench" in body["bio"]


@pytest.mark.asyncio
async def test_add_bio_addendum_rejects_short_text(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = await async_client.post(
        f"/dwellers/{uuid4()}/bio/addendum/",
        json={"text": "short"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 422


async def _set_radiated_state(async_session: AsyncSession, dweller: Dweller) -> None:
    dweller.max_health = 100
    dweller.health = 30
    dweller.radiation = 40
    dweller.stimpack = 1
    async_session.add(dweller)
    await async_session.commit()


@pytest.mark.asyncio
async def test_read_dweller_exposes_effective_max_health(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    dweller: Dweller,
) -> None:
    """DwellerReadFull must carry the radiation-reduced health ceiling."""
    await _set_radiated_state(async_session, dweller)
    response = await async_client.get(f"/dwellers/{dweller.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    assert response.json()["effective_max_health"] == 60


@pytest.mark.asyncio
async def test_read_dweller_list_exposes_effective_max_health(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    dweller: Dweller,
) -> None:
    """DwellerReadLess (compact list shape) must carry the same ceiling."""
    await _set_radiated_state(async_session, dweller)
    response = await async_client.get("/dwellers/", headers=superuser_token_headers)
    assert response.status_code == 200
    by_id = {d["id"]: d for d in response.json()}
    assert by_id[str(dweller.id)]["effective_max_health"] == 60


@pytest.mark.asyncio
async def test_use_stimpack_clamps_healing_at_effective_max_health(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    dweller: Dweller,
) -> None:
    """Stimpack healing must stop at the radiation-reduced ceiling, not max_health."""
    from app.core.game_config import game_config

    await _set_radiated_state(async_session, dweller)
    response = await async_client.post(f"/dwellers/{dweller.id}/use_stimpack", headers=superuser_token_headers)
    assert response.status_code == 200
    heal_amount = max(1, int(100 * game_config.health.stimpack_heal_percent))
    body = response.json()
    assert body["health"] == min(30 + heal_amount, 60)
    assert body["effective_max_health"] == 60


@pytest.mark.asyncio
async def test_revival_cost_endpoint_delegates_to_death_service() -> None:
    """The quote endpoint must reuse the service cost path, not recompute it inline."""
    from app.api.v1.endpoints.dweller import get_revival_cost as get_revival_cost_endpoint
    from app.schemas.dweller import RevivalCostResponse

    user = MagicMock()
    session = MagicMock()
    dweller_id = uuid4()
    expected = RevivalCostResponse(
        dweller_id=dweller_id,
        dweller_name="Casey Jones",
        level=7,
        revival_cost=525,
        days_until_permanent=5,
        can_afford=True,
        vault_caps=1000,
    )

    with (
        patch("app.api.v1.endpoints.dweller.verify_dweller_access", new=AsyncMock()),
        patch(
            "app.api.v1.endpoints.dweller.death_service.build_revival_quote",
            new=AsyncMock(return_value=expected),
        ) as build_quote,
    ):
        result = await get_revival_cost_endpoint(dweller_id=dweller_id, user=user, db_session=session)

    assert result is expected
    build_quote.assert_awaited_once_with(session, dweller_id, user)


@pytest.mark.asyncio
async def test_revive_endpoint_delegates_to_death_service() -> None:
    """The revive endpoint must not re-derive the cost; the service owns it."""
    from app.api.v1.endpoints.dweller import revive_dweller as revive_dweller_endpoint

    user = MagicMock()
    session = MagicMock()
    dweller_id = uuid4()
    expected = MagicMock()

    with (
        patch("app.api.v1.endpoints.dweller.verify_dweller_access", new=AsyncMock()),
        patch(
            "app.api.v1.endpoints.dweller.death_service.revive_dweller",
            new=AsyncMock(return_value=expected),
        ) as revive,
    ):
        result = await revive_dweller_endpoint(dweller_id=dweller_id, user=user, db_session=session)

    assert result is expected
    revive.assert_awaited_once_with(session, dweller_id, user)


@pytest.mark.asyncio
async def test_revival_endpoints_reject_users_without_vault_access(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Both revival endpoints map a failed ownership check to 403."""
    from app.utils.exceptions import AccessDeniedException

    dweller_id = uuid4()
    denial = AccessDeniedException("The user doesn't have enough privileges")

    with patch("app.api.v1.endpoints.dweller.verify_dweller_access", new=AsyncMock(side_effect=denial)):
        cost_response = await async_client.get(f"/dwellers/{dweller_id}/revival_cost", headers=superuser_token_headers)
        revive_response = await async_client.post(f"/dwellers/{dweller_id}/revive", headers=superuser_token_headers)

    assert cost_response.status_code == 403
    assert revive_response.status_code == 403


@pytest.mark.asyncio
async def test_update_dweller_rejects_game_state(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    dweller: Dweller,
) -> None:
    """A client must not be able to write game state the simulation owns."""
    original_level, original_health = dweller.level, dweller.health

    for payload in ({"level": 50}, {"health": 1500}, {"radiation": 0}, {"is_dead": True}, {"status": "working"}):
        response = await async_client.put(f"/dwellers/{dweller.id}", json=payload, headers=superuser_token_headers)
        assert response.status_code == 422, f"{payload} was accepted"

    await async_session.refresh(dweller)
    assert dweller.level == original_level
    assert dweller.health == original_health


@pytest.mark.asyncio
async def test_update_dweller_accepts_player_editable_fields(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    dweller: Dweller,
) -> None:
    """Renaming and appearance edits still work through the player-facing schema."""
    response = await async_client.put(
        f"/dwellers/{dweller.id}",
        json={"first_name": "Renamed", "visual_attributes": {"race": "human"}},
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    assert response.json()["first_name"] == "Renamed"
    await async_session.refresh(dweller)
    assert dweller.first_name == "Renamed"


@pytest.mark.asyncio
async def test_update_dweller_can_unassign_a_room(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    dweller: Dweller,
    room: Room,
) -> None:
    """The dweller roster unassigns by PUTting room_id: null."""
    dweller.room_id = room.id
    async_session.add(dweller)
    await async_session.commit()

    response = await async_client.put(
        f"/dwellers/{dweller.id}", json={"room_id": None}, headers=superuser_token_headers
    )

    assert response.status_code == 200
    await async_session.refresh(dweller)
    assert dweller.room_id is None


@pytest.mark.asyncio
async def test_dweller_detail_exposes_identity_modifiers(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    dweller: Dweller,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dossier can explain why a dweller is effective without recomputing rules client-side."""
    from app.core.game_config import game_config

    # The subsystem ships dark, so this test states the flag as a precondition.
    monkeypatch.setattr(game_config.features, "race_faction_mechanics", True)
    dweller.visual_attributes = {"race": "super_mutant", "faction": "super_mutant_tribe"}
    async_session.add(dweller)
    await async_session.commit()

    response = await async_client.get(f"/dwellers/{dweller.id}", headers=superuser_token_headers)

    assert response.status_code == 200
    modifiers = response.json()["identity_modifiers"]
    assert modifiers["strength"] == 3
    assert modifiers["perception"] == -2
    assert modifiers["radiation_immune"] is False
    assert modifiers["melee_damage_pct"] == 0.15
