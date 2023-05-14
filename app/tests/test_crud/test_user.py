from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app import crud
from app.core.security import verify_password
from app.schemas.user import UserCreate, UserUpdate
from app.tests.factory.users import create_fake_user
from app.tests.utils.utils import random_lower_string


def test_create_user(session: Session) -> None:
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = crud.user.create(session, obj_in=user_in)
    assert user.email == user_data["email"]
    assert hasattr(user, "hashed_password")


def test_authenticate_user(session: Session) -> None:
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = crud.user.create(session, obj_in=user_in)
    authenticated_user = crud.user.authenticate(session, email=user_data["email"], password=user_data["password"])
    assert authenticated_user
    assert user.email == authenticated_user.email


def test_not_authenticate_user(session: Session) -> None:
    user_data = create_fake_user()
    user = crud.user.authenticate(session, email=user_data["email"], password=user_data["password"])
    assert user is None


def test_check_if_user_is_active(session: Session) -> None:
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = crud.user.create(session, obj_in=user_in)
    is_active = crud.user.is_active(user)
    assert is_active is True


def test_check_if_user_is_active_inactive(session: Session) -> None:
    user_data = create_fake_user()
    user_in = UserCreate(**user_data, is_active=True)
    user = crud.user.create(session, obj_in=user_in)
    is_active = crud.user.is_active(user)
    assert is_active


def test_check_if_user_is_superuser(session: Session) -> None:
    user_data = create_fake_user()
    user_in = UserCreate(**user_data, is_superuser=True)
    user = crud.user.create(session, obj_in=user_in)
    is_superuser = crud.user.is_superuser(user)
    assert is_superuser is True


def test_check_if_user_is_superuser_normal_user(session: Session) -> None:
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = crud.user.create(session, obj_in=user_in)
    is_superuser = crud.user.is_superuser(user)
    assert is_superuser is False


def test_get_user(session: Session) -> None:
    user_data = create_fake_user()
    user_in = UserCreate(**user_data, is_superuser=True)
    user = crud.user.create(session, obj_in=user_in)
    user_2 = crud.user.get(session, id=user.id)
    assert user_2
    assert user.email == user_2.email
    assert jsonable_encoder(user) == jsonable_encoder(user_2)


def test_update_user(session: Session) -> None:
    user_data = create_fake_user()
    user_in = UserCreate(**user_data, is_superuser=True)
    user = crud.user.create(session, obj_in=user_in)
    new_password = random_lower_string()
    user_in_update = UserUpdate(password=new_password, is_superuser=True)
    crud.user.update(session, id=user.id, obj_in=user_in_update)
    user_2 = crud.user.get(session, id=user.id)
    assert user_2
    assert user.email == user_2.email
    assert verify_password(new_password, user_2.hashed_password)
