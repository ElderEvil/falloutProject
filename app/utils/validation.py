from pydantic import UUID4

from app.utils.exceptions import AccessDeniedException, InvalidVaultTransferException


def validate_user_permission(user_id: UUID4, resource_owner_id: UUID4):
    if user_id != resource_owner_id:
        raise AccessDeniedException(detail="You do not have permission to access this resource.")


def validate_vault_transfer(source_vault_id: UUID4, target_vault_id: UUID4):
    if source_vault_id != target_vault_id:
        raise InvalidVaultTransferException
