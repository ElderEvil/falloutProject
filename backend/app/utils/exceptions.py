"""Domain exceptions.

Transport-free by contract (``docs/backend/SERVICE_LAYER.md``): these classes carry HTTP semantics
as plain data attributes (``status_code``/``detail``/``headers``) but never inherit
``fastapi.HTTPException``. Services raise them; the API layer (``main.py``) owns the single mapping
to responses via ``domain_exception_handler``.
"""

from typing import Any
from uuid import UUID

from sqlmodel import SQLModel
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse


class DomainError(Exception):
    """Base for all domain exceptions; mapped to HTTP only at the API boundary."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail: str = "An unexpected error occurred."

    def __init__(self, detail: str | None = None, headers: dict[str, Any] | None = None) -> None:
        self.detail = detail if detail is not None else self.default_detail
        self.headers = headers
        super().__init__(self.detail)


def domain_exception_handler(_request: Request, exc: DomainError) -> JSONResponse:
    """Map a domain exception to its HTTP response. The only transport mapping point."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)


class AccessDeniedException(DomainError):
    """Raised when a user attempts an action without the necessary permissions."""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Access denied due to insufficient permissions."


class ResourceNotFoundException(DomainError):
    """Raised when a resource identified by its unique identifier or name is not found."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(
        self,
        model: type[SQLModel],
        identifier: str | UUID,
        identifier_type: str = "id",
        headers: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"Unable to find the {model.__name__} with {identifier_type} {identifier}.", headers)


class ResourceAlreadyExistsException(DomainError):
    """Raised when creating or updating a resource would violate unique constraints."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, model: type[SQLModel], name: str, headers: dict[str, Any] | None = None) -> None:
        super().__init__(f"The {model.__name__} name {name} already exists.", headers)


class ResourceConflictException(DomainError):
    """Generic exception for handling conflicts during operations on resources."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Resource conflict encountered."


class ContentNoChangeException(DomainError):
    """Raised when an attempted update operation does not change any data."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "No changes detected in the content update."


class ValidationException(DomainError):
    """Raised when validation fails for a domain operation."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Validation failed."


class NotFoundException(DomainError):
    """Raised when a requested resource is not found."""

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Not found."


class InvalidItemAssignmentException(DomainError):
    """Raised when attempting to assign an item to both a storage and a dweller."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, model: type[SQLModel], headers: dict[str, Any] | None = None) -> None:
        super().__init__(f"The {model.__name__} cannot be assigned to both a storage and a dweller.", headers)


class InvalidVaultTransferException(ContentNoChangeException):
    """Raised when attempting to move an item between vaults."""

    default_detail = "Items can only be moved within the same vault."


class VaultOperationException(DomainError):
    """Base exception for errors that occur during operations within the vault."""

    def __init__(
        self, detail: str, headers: dict[str, Any] | None = None, status_code: int = status.HTTP_400_BAD_REQUEST
    ) -> None:
        self.status_code = status_code
        super().__init__(detail, headers)


class IncidentsDisabledException(VaultOperationException):
    """Raised when an incident spawn is attempted on a vault with incidents disabled."""

    def __init__(self, headers: dict[str, Any] | None = None) -> None:
        super().__init__("Incidents are disabled for this vault.", headers)


class NoSpaceAvailableException(VaultOperationException):
    """Raised when attempting to build a room in a vault with no available space."""

    def __init__(self, space_needed: int | None = None, headers: dict[str, Any] | None = None) -> None:
        detail = "No available space in vault to place the new room."
        if space_needed is not None:
            detail += f" {space_needed} units of space needed."
        super().__init__(detail, headers)


class InsufficientResourcesException(VaultOperationException):
    """Raised when attempting to perform an action without sufficient resources."""

    def __init__(
        self,
        resource_name: str | None = None,
        resource_amount: int | None = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        detail = "Insufficient resources to perform the action."
        if resource_name and resource_amount is not None:
            detail += f" Not enough {resource_name}; {resource_amount} more needed."
        super().__init__(detail, headers)


class UniqueRoomViolationException(VaultOperationException):
    """Raised when attempting to create a room that violates the unique room constraint."""

    def __init__(self, room_name: str | None = None, headers: dict[str, Any] | None = None) -> None:
        detail = "A unique room of this type already exists in the vault."
        if room_name is not None:
            detail += f" Room name: {room_name}."
        super().__init__(detail, headers)


class DwellerNotFoundError(NotFoundException):
    """Raised when a dweller is not found."""


class QuotaExceededException(DomainError):
    """Raised when a user exceeds their monthly token quota."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Monthly token quota exceeded. Please try again next month or contact support."


class AIProviderCreditsExhaustedException(DomainError):
    """Raised when the configured AI provider has no remaining credits."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "AI provider credits are exhausted. Please try again later."


class AIProviderException(DomainError):
    """Raised when an AI provider call fails in a retryable way."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "AI provider request failed. Please try again."


class AIStorageException(DomainError):
    """Raised when media storage is unavailable or disabled."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Storage service is not available."


class AIAudioException(DomainError):
    """Raised when audio generation fails."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Failed to generate audio. Please try again."


class BucketNotFoundError(DomainError):
    """Raised when a storage bucket is not found or cannot be created."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Storage bucket not found."


class FileUploadError(DomainError):
    """Raised when a file upload operation fails."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "File upload failed."


class FileDownloadError(DomainError):
    """Raised when a file download operation fails."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "File download failed."


class EmailDeliveryException(DomainError):
    """Raised when an outbound email cannot be delivered via the configured SMTP server."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Failed to deliver email via the configured SMTP server."
