from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import crud
from app.core.config import settings
from app.schemas.user import UserCreate
from app.tests.factory.users import create_fake_user


def test_get_users_superuser_me(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    r = client.get(f"{settings.API_V1_STR}/users/me", headers=superuser_token_headers)
    current_user = r.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["is_superuser"]
    assert current_user["email"] == settings.FIRST_SUPERUSER_EMAIL


def test_get_users_normal_user_me(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    r = client.get(f"{settings.API_V1_STR}/users/me", headers=normal_user_token_headers)
    current_user = r.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["is_superuser"] is False
    assert current_user["email"] == settings.EMAIL_TEST_USER


def test_create_user_new_email(
    client: TestClient,
    superuser_token_headers: dict,
    session: Session,
) -> None:
    user_data = create_fake_user()
    r = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=superuser_token_headers,
        json=user_data,
    )
    assert 200 <= r.status_code < 300
    created_user = r.json()
    user = crud.user.get_by_email(db=session, email=user_data["email"])
    assert user
    assert user.email == created_user["email"]


def test_get_existing_user(
    client: TestClient,
    superuser_token_headers: dict,
    session: Session,
) -> None:
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = crud.user.create(db=session, obj_in=user_in)
    user_id = user.id
    r = client.get(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=superuser_token_headers,
    )
    assert 200 <= r.status_code < 300
    api_user = r.json()
    existing_user = crud.user.get_by_email(db=session, email=user_data["email"])
    assert existing_user
    assert existing_user.email == api_user["email"]


def test_create_user_existing_username(
    client: TestClient,
    superuser_token_headers: dict,
    session: Session,
) -> None:
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    crud.user.create(db=session, obj_in=user_in)
    r = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=superuser_token_headers,
        json=user_data,
    )
    created_user = r.json()
    assert r.status_code == 400
    assert "_id" not in created_user


def test_create_user_by_normal_user(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    user_data = create_fake_user()
    r = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=normal_user_token_headers,
        json=user_data,
    )
    assert r.status_code == 400


def test_retrieve_users(
    client: TestClient,
    superuser_token_headers: dict,
    session: Session,
) -> None:
    user_1_data = create_fake_user()
    user_1_in = UserCreate(**user_1_data)
    crud.user.create(db=session, obj_in=user_1_in)

    user_2_data = create_fake_user()
    user_2_in = UserCreate(**user_2_data)
    crud.user.create(db=session, obj_in=user_2_in)

    r = client.get(f"{settings.API_V1_STR}/users/", headers=superuser_token_headers)
    all_users = r.json()

    assert len(all_users) > 1
    for item in all_users:
        assert "email" in item
