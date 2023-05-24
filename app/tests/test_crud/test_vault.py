from sqlmodel import Session

from app import crud
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


def test_create_vault_with_user(session: Session) -> None:
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = crud.user.create(session, obj_in=user_in)
    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = crud.vault.create(session, obj_in=vault_in)

    assert vault.user_id == user.id
