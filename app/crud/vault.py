from pydantic import UUID4
from sqlmodel import Session

from app.crud.base import CRUDBase
from app.models.vault import Vault
from app.schemas.vault import VaultCreate, VaultCreateWithUserID, VaultUpdate


class CRUDVault(CRUDBase[Vault, VaultCreate, VaultUpdate]):
    def get_by_user_id(self, db: Session, *, user_id: int):
        return db.query(self.model).filter(Vault.user_id == user_id).all()

    def create_with_user_id(self, db: Session, obj_in: VaultCreate, user_id: UUID4) -> Vault:
        obj_data = obj_in.dict()
        obj_data["user_id"] = user_id
        obj_in = VaultCreateWithUserID(**obj_data)
        return super().create(db, obj_in)


vault = CRUDVault(Vault)
