from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import crud
from app.core.config import settings
from app.schemas.vault import VaultCreate
from app.tests.factory.vaults import create_fake_vault


def test_vault_create(client: TestClient, session: Session, normal_user_token_headers: dict[str, str]):
    user = crud.user.get_by_email(session, email=settings.EMAIL_TEST_USER)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    response = client.post(f"{settings.API_V1_STR}/vaults/", headers=normal_user_token_headers, json=vault_data)
    assert response.status_code == 201


def test_vault_read_list(client: TestClient, session: Session):
    pass


def test_vault_read(client: TestClient, session: Session, superuser_token_headers: dict[str, str]):
    user = crud.user.get_by_email(session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_to_create = VaultCreate(**vault_data)
    created_vault = crud.vault.create(session, vault_to_create)

    response = client.get(f"{settings.API_V1_STR}/vaults/{created_vault.id}/", headers=superuser_token_headers)

    assert response.status_code == 200

    response_data = response.json()
    assert response_data["id"] == str(created_vault.id)
    assert response_data["name"] == vault_data["name"]
    assert response_data["bottle_caps"] == vault_data["bottle_caps"]
    assert response_data["happiness"] == vault_data["happiness"]
    # assert response_data["user_id"] == vault_data["user_id"]  # TODO: Fix this


def test_vault_update(client: TestClient, session: Session):
    pass


def test_vault_delete(client: TestClient, session: Session):
    pass
