from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.models.weapon import Weapon
from main import app
from utils.common import Rarity


def test_create_weapon(client: TestClient):
    response = client.post(
        "/weapons/", json={
            "name": "Blade of Woe",
            "weapon_type": "Melee",
            "weapon_subtype": "Pointed",
            "rarity": Rarity.legendary,
            "stat": "agility",
            "damage_min": 13,
            "damage_max": 26,
        }
    )
    app.dependency_overrides.clear()
    data = response.json()

    assert response.status_code == 200
    assert data["name"] == "Blade of Woe"
    assert data["weapon_type"] == "Melee"
    assert data["weapon_subtype"] == "Pointed"
    assert data["stat"] == "agility"
    assert data["damage_min"] == 13
    assert data["damage_max"] == 26
    assert data["id"] is not None


def test_create_hero_incomplete(client: TestClient):
    response = client.post("/weapons/", json={"name": "Blade of Woe"})
    assert response.status_code == 422


def test_create_hero_invalid(client: TestClient):
    response = client.post(
        "/weapons/",
        json={
            "name": "Blade of Woe",
            "weapon_type": {"message": "Do you wanna know weapon type?"},
        },
    )
    assert response.status_code == 422


def test_read_weapons(session: Session, client: TestClient):
    weapon_1 = Weapon(**{
        "name": "Blade of Woe",
        "weapon_type": "Melee",
        "weapon_subtype": "Pointed",
        "rarity": Rarity.legendary,
        "stat": "agility",
        "damage_min": 13,
        "damage_max": 26,
    })
    weapon_2 = Weapon(**{
        "name": "Death adder",
        "weapon_type": "Melee",
        "weapon_subtype": "Pointed",
        "rarity": Rarity.legendary,
        "stat": "agility",
        "damage_min": 11,
        "damage_max": 22,
        "value": 1000,
    })
    session.add(weapon_1)
    session.add(weapon_2)
    session.commit()

    response = client.get("/weapons/")
    data = response.json()

    assert response.status_code == 200

    assert len(data) == 2
    assert data[0]["name"] == weapon_1.name
    # assert data[0]["secret_name"] == weapon_1.secret_name
    # assert data[0]["age"] == weapon_1.age
    assert data[0]["id"] == weapon_1.id
    assert data[1]["name"] == weapon_2.name
    # assert data[1]["secret_name"] == weapon_2.secret_name
    # assert data[1]["age"] == weapon_2.age
    assert data[1]["id"] == weapon_2.id


# def test_read_hero(session: Session, client: TestClient):
#     hero_1 = Weapon(name="Deadpond", secret_name="Dive Wilson")
#     session.add(hero_1)
#     session.commit()
#
#     response = client.get(f"/heroes/{hero_1.id}")
#     data = response.json()
#
#     assert response.status_code == 200
#     assert data["name"] == hero_1.name
#     assert data["secret_name"] == hero_1.secret_name
#     assert data["age"] == hero_1.age
#     assert data["id"] == hero_1.id
#
#
# def test_update_hero(session: Session, client: TestClient):
#     hero_1 = Hero(name="Deadpond", secret_name="Dive Wilson")
#     session.add(hero_1)
#     session.commit()
#
#     response = client.patch(f"/heroes/{hero_1.id}", json={"name": "Deadpuddle"})
#     data = response.json()
#
#     assert response.status_code == 200
#     assert data["name"] == "Deadpuddle"
#     assert data["secret_name"] == "Dive Wilson"
#     assert data["age"] is None
#     assert data["id"] == hero_1.id
#
#
# def test_delete_hero(session: Session, client: TestClient):
#     hero_1 = Hero(name="Deadpond", secret_name="Dive Wilson")
#     session.add(hero_1)
#     session.commit()
#
#     response = client.delete(f"/heroes/{hero_1.id}")
#
#     hero_in_db = session.get(Hero, hero_1.id)
#
#     assert response.status_code == 200
#
#     assert hero_in_db is None
