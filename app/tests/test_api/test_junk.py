import random

from sqlmodel import Session
from starlette.testclient import TestClient

from app import crud
from app.core.config import settings
from app.schemas.common import JunkType
from app.schemas.junk import JunkCreate
from app.tests.utils.utils import random_lower_string


def test_create_junk(client: TestClient, junk_data: dict):
    r = client.post(f"{settings.API_V1_STR}/junk", json=junk_data)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == junk_data["name"]
    assert data["rarity"] == junk_data["rarity"]
    assert data["value"] == junk_data["value"]
    assert data["junk_type"] == junk_data["junk_type"]
    assert data["description"] == junk_data["description"]


def test_read_junk_list(client: TestClient, session: Session, junk_data: dict):
    junk_data_2 = {
        "name": random_lower_string(16).capitalize(),
        "rarity": "Common",
        "value": random.randint(1, 1000),
        "junk_type": random.choice(list(JunkType)),
        "description": random_lower_string(16),
    }
    junk_obj_1 = JunkCreate(**junk_data)
    junk_obj_2 = JunkCreate(**junk_data_2)
    crud.junk.create(session, junk_obj_1)
    crud.junk.create(session, junk_obj_2)
    r = client.get(f"{settings.API_V1_STR}/junk/")
    assert r.status_code == 200


def test_read_junk(client: TestClient, session: Session, junk_data: dict):
    junk_obj = JunkCreate(**junk_data)
    junk_item = crud.junk.create(session, junk_obj)
    r = client.get(f"{settings.API_V1_STR}/junk/{junk_item.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == junk_data["name"]
    assert data["rarity"] == junk_data["rarity"]
    assert data["value"] == junk_data["value"]
    assert data["junk_type"] == junk_data["junk_type"]
    assert data["description"] == junk_data["description"]


def test_update_junk(client: TestClient, session: Session, junk_data: dict):
    r = client.post(f"{settings.API_V1_STR}/junk/", json=junk_data)
    junk_item = r.json()
    junk_new_data = {
        "name": random_lower_string(16).capitalize(),
        "rarity": "Legendary",
        "value": random.randint(1, 1000),
        "junk_type": random.choice(list(JunkType)),
        "description": random_lower_string(16),
    }
    update_response = client.put(f"{settings.API_V1_STR}/junk/{junk_item['id']}", json=junk_new_data)
    updated_junk = update_response.json()
    assert update_response.status_code == 200
    assert updated_junk["name"] == junk_new_data["name"]
    assert updated_junk["rarity"] == junk_new_data["rarity"]
    assert updated_junk["value"] == junk_new_data["value"]
    assert updated_junk["junk_type"] == junk_new_data["junk_type"]
    assert updated_junk["description"] == junk_new_data["description"]


def test_delete_junk(client: TestClient, session: Session, junk_data: dict):
    create_response = client.post(f"{settings.API_V1_STR}/junk/", json=junk_data)
    junk_item = create_response.json()
    delete_response = client.delete(f"{settings.API_V1_STR}/junk/{junk_item['id']}")
    assert delete_response.status_code == 204
