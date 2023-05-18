from sqlmodel import Session

from app.crud.base import CRUDBase
from app.models.vault import Vault
from app.schemas.vault import VaultCreate, VaultUpdate


class CRUDVault(CRUDBase[Vault, VaultCreate, VaultUpdate]):
    def get_by_user_id(self, db: Session, *, user_id: int):
        return db.query(self.model).filter(Vault.user_id == user_id).all()


vault = CRUDVault(Vault)
