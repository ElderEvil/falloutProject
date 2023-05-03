from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.crud.user import crud_user
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import verify_password
from app.tests.utils.utils import random_email, random_lower_string


def test_create_user(session: Session) -> None:
    username = random_lower_string(k=10)
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(username=username, email=email, password=password)
    user = crud_user.create(session, obj_in=user_in)
    assert user.email == email
    assert hasattr(user, "hashed_password")


def test_authenticate_user(session: Session) -> None:
    username = random_lower_string(k=10)
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(username=username, email=email, password=password)
    user = crud_user.create(session, obj_in=user_in)
    authenticated_user = crud_user.authenticate(session, email=email, password=password)
    assert authenticated_user
    assert user.email == authenticated_user.email


def test_not_authenticate_user(session: Session) -> None:
    email = random_email()
    password = random_lower_string()
    user = crud_user.authenticate(session, email=email, password=password)
    assert user is None


def test_check_if_user_is_active(session: Session) -> None:
    username = random_lower_string(k=10)
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(username=username, email=email, password=password)
    user = crud_user.create(session, obj_in=user_in)
    is_active = crud_user.is_active(user)
    assert is_active is True


def test_check_if_user_is_active_inactive(session: Session) -> None:
    username = random_lower_string(k=10)
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(username=username, email=email, password=password, is_active=True)
    user = crud_user.create(session, obj_in=user_in)
    is_active = crud_user.is_active(user)
    assert is_active


def test_check_if_user_is_superuser(session: Session) -> None:
    username = random_lower_string(k=10)
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(username=username, email=email, password=password, is_superuser=True)
    user = crud_user.create(session, obj_in=user_in)
    is_superuser = crud_user.is_superuser(user)
    assert is_superuser is True


def test_check_if_user_is_superuser_normal_user(session: Session) -> None:
    username = random_lower_string()
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(username=username, email=email, password=password)
    user = crud_user.create(session, obj_in=user_in)
    is_superuser = crud_user.is_superuser(user)
    assert is_superuser is False


def test_get_user(session: Session) -> None:
    username = random_lower_string()
    password = random_lower_string()
    email = random_email()
    user_in = UserCreate(username=username, email=email, password=password, is_superuser=True)
    user = crud_user.create(session, obj_in=user_in)
    user_2 = crud_user.get(session, id=user.id)
    assert user_2
    assert user.email == user_2.email
    assert jsonable_encoder(user) == jsonable_encoder(user_2)


def test_update_user(session: Session) -> None:
    password = random_lower_string()
    email = random_email()
    username = random_lower_string(16)
    user_in = UserCreate(username=username, email=email, password=password, is_superuser=True)
    user = crud_user.create(session, obj_in=user_in)
    new_password = random_lower_string()
    user_in_update = UserUpdate(password=new_password, is_superuser=True)
    crud_user.update(session, id=user.id, obj_in=user_in_update)
    user_2 = crud_user.get(session, id=user.id)
    assert user_2
    assert user.email == user_2.email
    assert verify_password(new_password, user_2.hashed_password)
