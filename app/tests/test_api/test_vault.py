from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import crud
from app.core.config import settings
from app.schemas.vault import VaultCreate
from app.tests.factory.vaults import create_fake_vault


def test_vault_create(client: TestClient, session: Session):
    vault_data = create_fake_vault()
    r = client.post(f"{settings.API_V1_STR}/vaults/", json=vault_data)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == vault_data["name"]
    assert data["bottle_caps"] == vault_data["bottle_caps"]
    assert data["happiness"] == vault_data["happiness"]
    # assert data["user_id"] == vault_data["user_id"]


def test_vault_read_list(client: TestClient, session: Session):
    pass


def test_vault_read(client: TestClient, session: Session):
    vault_data = create_fake_vault()
    vault_to_create = VaultCreate(**vault_data)
    created_vault = crud.vault.create(session, vault_to_create)

    response = client.get(f"{settings.API_V1_STR}/weapons/{created_vault.id}/")

    assert response.status_code == 200

    response_vault = response.json()
    assert response_vault["name"] == vault_to_create.name
    assert response_vault["bottle_caps"] == vault_to_create.bottle_caps
    assert response_vault["happiness"] == vault_to_create.happiness
    assert response_vault["user_id"] == vault_to_create.user_id


def test_vault_update(client: TestClient, session: Session):
    pass


def test_vault_delete(client: TestClient, session: Session):
    pass
