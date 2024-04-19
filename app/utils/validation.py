from pydantic import UUID4

from app.utils.exceptions import InvalidVaultTransferException


def validate_vault_transfer(source_vault_id: UUID4, target_vault_id: UUID4):
    if source_vault_id != target_vault_id:
        raise InvalidVaultTransferException
