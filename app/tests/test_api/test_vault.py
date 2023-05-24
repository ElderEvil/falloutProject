from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import crud
from app.core.config import settings
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.vaults import create_fake_vault


def test_create_vault(client: TestClient, session: Session, normal_user_token_headers: dict[str, str]):
    user = crud.user.get_by_email(session, email=settings.EMAIL_TEST_USER)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    response = client.post(f"{settings.API_V1_STR}/vaults/", headers=normal_user_token_headers, json=vault_data)
    assert response.status_code == 201


def test_read_vault_list(client: TestClient, session: Session, superuser_token_headers: dict[str, str]):
    user = crud.user.get_by_email(session, email=settings.EMAIL_TEST_USER)
    vault_1_data, vault_2_data = create_fake_vault(), create_fake_vault()
    vault_1_data["user_id"] = vault_2_data["user_id"] = str(user.id)
    crud.vault.create(session, VaultCreateWithUserID(**vault_1_data))
    crud.vault.create(session, VaultCreateWithUserID(**vault_2_data))

    response = client.get(f"{settings.API_V1_STR}/vaults/", headers=superuser_token_headers)

    assert response.status_code == 200

    response_data = response.json()
    assert len(response_data) > 1


def test_read_vault(client: TestClient, session: Session, superuser_token_headers: dict[str, str]):
    user = crud.user.get_by_email(session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_to_create = VaultCreateWithUserID(**vault_data)
    created_vault = crud.vault.create(session, vault_to_create)

    response = client.get(f"{settings.API_V1_STR}/vaults/{created_vault.id}/", headers=superuser_token_headers)

    assert response.status_code == 200

    response_data = response.json()
    assert response_data["id"] == str(created_vault.id)
    assert response_data["name"] == vault_data["name"]
    assert response_data["bottle_caps"] == vault_data["bottle_caps"]
    assert response_data["happiness"] == vault_data["happiness"]
    assert response_data["user_id"] == vault_data["user_id"]


def test_update_vault(client: TestClient, session: Session, superuser_token_headers: dict[str, str]):
    user = crud.user.get_by_email(session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_to_create = VaultCreateWithUserID(**vault_data)
    created_vault = crud.vault.create(session, vault_to_create)

    response = client.get(f"{settings.API_V1_STR}/vaults/{created_vault.id}/", headers=superuser_token_headers)

    assert response.status_code == 200

    new_vault_data = create_fake_vault()
    new_vault_data["user_id"] = str(user.id)

    update_response = client.put(
        f"{settings.API_V1_STR}/vaults/{created_vault.id}/",
        json=new_vault_data,
        headers=superuser_token_headers,
    )

    assert update_response.status_code == 200

    update_response_data = update_response.json()
    assert update_response_data["id"] == str(created_vault.id)
    assert update_response_data["name"] == new_vault_data["name"]
    assert update_response_data["bottle_caps"] == new_vault_data["bottle_caps"]
    assert update_response_data["happiness"] == new_vault_data["happiness"]
    assert update_response_data["user_id"] == vault_data["user_id"]


def test_delete_vault(client: TestClient, session: Session, superuser_token_headers: dict[str, str]):
    user = crud.user.get_by_email(session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_to_create = VaultCreateWithUserID(**vault_data)
    created_vault = crud.vault.create(session, vault_to_create)

    response = client.get(f"{settings.API_V1_STR}/vaults/{created_vault.id}/", headers=superuser_token_headers)

    assert response.status_code == 200

    delete_response = client.delete(
        f"{settings.API_V1_STR}/vaults/{created_vault.id}/",
        headers=superuser_token_headers,
    )

    assert delete_response.status_code == 204
