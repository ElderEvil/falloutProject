from starlette.testclient import TestClient

from app.core.config import settings


def test_create_junk(client: TestClient, junk_data: dict):
    r = client.post(f"{settings.API_V1_STR}/junk", json=junk_data)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == junk_data["name"]
    assert data["rarity"] == junk_data["rarity"]
    assert data["value"] == junk_data["value"]


def test_read_junk_list():
    assert True


def test_read_junk():
    assert True


def test_update_junk():
    assert True


def test_delete_junk():
    assert True
