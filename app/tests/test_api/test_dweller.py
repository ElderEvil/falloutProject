from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app import crud
from app.schemas.dweller import DwellerCreate
from app.tests.factory.dwellers import create_fake_dweller


def test_create_dweller(client: TestClient):
    dweller_data = create_fake_dweller()
    response = client.post(f"{settings.API_V1_STR}/dwellers/", json=dweller_data)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["first_name"] == dweller_data["first_name"]
    assert response_data["last_name"] == dweller_data["last_name"]
    assert response_data["rarity"] == dweller_data["rarity"]
    assert response_data["level"] == dweller_data["level"]
    assert response_data["experience"] == dweller_data["experience"]
    assert response_data["max_health"] == dweller_data["max_health"]
    assert response_data["health"] == dweller_data["health"]
    assert response_data["happiness"] == dweller_data["happiness"]
    assert response_data["is_adult"] == dweller_data["is_adult"]


def test_read_dwellers(session: Session, client: TestClient):
    dweller_1_data = create_fake_dweller()
    dweller_2_data = create_fake_dweller()

    dweller_1 = DwellerCreate(**dweller_1_data)
    crud.dweller.create(session, dweller_1)

    dweller_2 = DwellerCreate(**dweller_2_data)
    crud.dweller.create(session, dweller_2)

    response = client.get(f"{settings.API_V1_STR}/dwellers/")

    assert response.status_code == 200


def test_read_dweller(session: Session, client: TestClient):
    dweller_data = create_fake_dweller()

    dweller_1 = DwellerCreate(**dweller_data)
    created_dweller = crud.dweller.create(session, dweller_1)

    response = client.get(f"{settings.API_V1_STR}/dwellers/{created_dweller.id}/")

    assert response.status_code == 200

    response_dweller = response.json()
    assert response_dweller["name"] == dweller_1.name
    assert response_dweller["rarity"] == dweller_1.rarity.value
    assert response_dweller["dweller_type"] == dweller_1.dweller_type.value
    assert response_dweller["dweller_subtype"] == dweller_1.dweller_subtype.value
    assert response_dweller["stat"] == dweller_1.stat
    assert response_dweller["damage_min"] == dweller_1.damage_min
    assert response_dweller["damage_max"] == dweller_1.damage_max


def test_update_dweller(session: Session, client: TestClient):
    dweller_data = create_fake_dweller()
    response = client.post(f"{settings.API_V1_STR}/dwellers/", json=dweller_data)
    dweller_response = response.json()
    dweller_id = dweller_response["id"]
    dweller_new_data = create_fake_dweller()

    update_response = client.put(f"{settings.API_V1_STR}/dwellers/{dweller_id}", json=dweller_new_data)
    updated_dweller = update_response.json()

    assert update_response.status_code == 200
    assert updated_dweller["id"] == dweller_id
    assert updated_dweller["first_name"] == dweller_new_data["first_name"]
    assert updated_dweller["last_name"] == dweller_new_data["last_name"]
    assert updated_dweller["rarity"] == dweller_new_data["rarity"]


def test_delete_dweller(session: Session, client: TestClient):
    dweller_data = create_fake_dweller()
    create_response = client.post(f"{settings.API_V1_STR}/dwellers/", json=dweller_data)
    created_dweller = create_response.json()

    delete_response = client.delete(f"{settings.API_V1_STR}/dwellers/{created_dweller['id']}")

    assert delete_response.status_code == 204

    # TODO Check that the dweller is actually deleted
    # read_response = client.get(f"{settings.API_V1_STR}/dwellers/{dweller_1['id']}")
    # assert read_response.status_code == 404
