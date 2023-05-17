from app.crud.base import CRUDBase
from app.models.vault import Vault
from app.schemas.vault import VaultCreate, VaultUpdate


class CRUDVault(CRUDBase[Vault, VaultCreate, VaultUpdate]):
    ...


vault = CRUDVault(Vault)
