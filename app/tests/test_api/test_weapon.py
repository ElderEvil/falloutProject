from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app import crud
from app.schemas.weapon import WeaponCreate


def test_create_weapon(client: TestClient):
    data = {
        "name": "Test Weapon",
        "rarity": "Common",
        "weapon_type": "Melee",
        "weapon_subtype": "Blunt",
        "stat": "strength",
        "damage_min": 5,
        "damage_max": 10,
    }
    response = client.post(f"{settings.API_V1_STR}/weapons/", json=data)
    response_data = response.json()

    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["rarity"] == data["rarity"]
    assert response_data["weapon_type"] == data["weapon_type"]
    assert response_data["weapon_subtype"] == data["weapon_subtype"]
    assert response_data["stat"] == data["stat"]
    assert response_data["damage_min"] == data["damage_min"]
    assert response_data["damage_max"] == data["damage_max"]


def test_create_weapon_incomplete(client: TestClient):
    response = client.post(
        f"{settings.API_V1_STR}/weapons/",
        json={"name": "Test Weapon"},
    )
    assert response.status_code == 422


def test_create_weapon_invalid(client: TestClient):
    response = client.post(
        f"{settings.API_V1_STR}/weapons/",
        json={
            "name": "Test Weapon",
            "rarity": "Unique",
            "weapon_type": ["Melee"],
        },
    )
    assert response.status_code == 422


def test_read_weapons(session: Session, client: TestClient):
    weapon_1_data = {
        "name": "Test Weapon",
        "rarity": "Common",
        "weapon_type": "Melee",
        "weapon_subtype": "Blunt",
        "stat": "strength",
        "damage_min": 5,
        "damage_max": 10,
    }
    weapon_2_data = {
        "name": "Test Weapon 2",
        "rarity": "Rare",
        "weapon_type": "Gun",
        "weapon_subtype": "Pistol",
        "stat": "agility",
        "damage_min": 7,
        "damage_max": 14,
    }

    weapon_1 = WeaponCreate(**weapon_1_data)
    # weapon.create(session, weapon_1) # TODO make tests independent of each other

    weapon_2 = WeaponCreate(**weapon_2_data)
    crud.weapon.create(session, weapon_2)

    response = client.get(f"{settings.API_V1_STR}/weapons/")
    all_weapons = response.json()

    assert response.status_code == 200
    # assert len(all_weapons) == 2  # TODO make tests independent of each other

    response_weapon_1, response_weapon_2 = all_weapons
    assert response_weapon_1["name"] == weapon_1.name
    assert response_weapon_1["rarity"] == weapon_1.rarity.value
    assert response_weapon_1["weapon_type"] == weapon_1.weapon_type.value
    assert response_weapon_1["weapon_subtype"] == weapon_1.weapon_subtype.value
    assert response_weapon_1["stat"] == weapon_1.stat
    assert response_weapon_1["damage_min"] == weapon_1.damage_min
    assert response_weapon_1["damage_max"] == weapon_1.damage_max

    assert response_weapon_2["name"] == weapon_2.name
    assert response_weapon_2["rarity"] == weapon_2.rarity.value
    assert response_weapon_2["weapon_type"] == weapon_2.weapon_type.value
    assert response_weapon_2["weapon_subtype"] == weapon_2.weapon_subtype.value
    assert response_weapon_2["stat"] == weapon_2.stat
    assert response_weapon_2["damage_min"] == weapon_2.damage_min
    assert response_weapon_2["damage_max"] == weapon_2.damage_max


def test_read_weapon(session: Session, client: TestClient):
    weapon_1_data = {
        "name": "Test Weapon",
        "rarity": "Common",
        "weapon_type": "Melee",
        "weapon_subtype": "Blunt",
        "stat": "strength",
        "damage_min": 5,
        "damage_max": 10,
    }

    weapon_1 = WeaponCreate(**weapon_1_data)
    crud.weapon.create(session, weapon_1)

    response = client.get(f"{settings.API_V1_STR}/weapons/1/")

    assert response.status_code == 200

    response_weapon = response.json()
    assert response_weapon["name"] == weapon_1.name
    assert response_weapon["rarity"] == weapon_1.rarity.value
    assert response_weapon["weapon_type"] == weapon_1.weapon_type.value
    assert response_weapon["weapon_subtype"] == weapon_1.weapon_subtype.value
    assert response_weapon["stat"] == weapon_1.stat
    assert response_weapon["damage_min"] == weapon_1.damage_min
    assert response_weapon["damage_max"] == weapon_1.damage_max


def test_update_weapon(session: Session, client: TestClient):
    weapon_data = {
        "name": "Test Weapon",
        "rarity": "Common",
        "weapon_type": "Melee",
        "weapon_subtype": "Blunt",
        "stat": "strength",
        "damage_min": 5,
        "damage_max": 10,
    }

    response = client.post(f"{settings.API_V1_STR}/weapons/", json=weapon_data)
    weapon_1 = response.json()
    weapon_id = weapon_1["id"]
    weapon_new_data = {
        "name": "Test Weapon 2",
        "rarity": "Rare",
        "weapon_type": "Gun",
        "weapon_subtype": "Pistol",
        "stat": "agility",
        "damage_min": 7,
        "damage_max": 14,
    }

    update_response = client.put(f"{settings.API_V1_STR}/weapons/{weapon_id}", json=weapon_new_data)
    updated_weapon = update_response.json()

    assert update_response.status_code == 200
    assert updated_weapon["id"] == weapon_id
    assert updated_weapon["name"] == weapon_new_data["name"]
    assert updated_weapon["rarity"] == weapon_new_data["rarity"]
    assert updated_weapon["weapon_type"] == weapon_new_data["weapon_type"]
    assert updated_weapon["weapon_subtype"] == weapon_new_data["weapon_subtype"]
    assert updated_weapon["stat"] == weapon_new_data["stat"]
    assert updated_weapon["damage_min"] == weapon_new_data["damage_min"]
    assert updated_weapon["damage_max"] == weapon_new_data["damage_max"]


def test_delete_weapon(session: Session, client: TestClient):
    data = {
        "name": "Test Weapon",
        "rarity": "Common",
        "weapon_type": "Melee",
        "weapon_subtype": "Blunt",
        "stat": "strength",
        "damage_min": 5,
        "damage_max": 10,
    }
    create_response = client.post(f"{settings.API_V1_STR}/weapons/", json=data)
    weapon_1 = create_response.json()

    delete_response = client.delete(f"{settings.API_V1_STR}/weapons/{weapon_1['id']}")

    assert delete_response.status_code == 204

    # TODO Check that the weapon is actually deleted
    # read_response = client.get(f"{settings.API_V1_STR}/weapons/{weapon_1['id']}")
    # assert read_response.status_code == 404
