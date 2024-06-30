from typing import Any, Generic, TypeVar
from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import SQLModel

ModelType = TypeVar("ModelType", bound=SQLModel)


class AccessDeniedException(HTTPException, Generic[ModelType]):
    """
    Exception raised when a user attempts to perform an action without the necessary permissions.

    :param detail: Optional detailed message to override the default error message.
    :param headers: Optional HTTP headers to be sent in the response.
    """

    def __init__(
        self, detail: str = "Access denied due to insufficient permissions.", headers: dict[str, Any] | None = None
    ) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail, headers=headers)


class ResourceNotFoundException(HTTPException, Generic[ModelType]):
    """
    Exception raised when a specific resource identified by its unique identifier or name is not found.

    :param model: The model class of the resource.
    :param identifier: The unique identifier or name of the resource.
    :param identifier_type: Type of identifier used ('id' or 'name').
    :param headers: Optional HTTP headers to be sent in the response.
    """

    def __init__(
        self,
        model: type[ModelType],
        identifier: str | UUID,
        identifier_type: str = "id",
        headers: dict[str, Any] | None = None,
    ) -> None:
        detail = f"Unable to find the {model.__name__} with {identifier_type} {identifier}."
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail, headers=headers)


class ResourceAlreadyExistsException(HTTPException, Generic[ModelType]):
    """
    Exception raised when attempting to create or update a resource that would violate unique constraints.

    :param model: The model class of the resource.
    :param name: The unique name that already exists.
    :param headers: Optional HTTP headers to be sent in the response.
    """

    def __init__(
        self,
        model: type[ModelType],
        name: str,
        headers: dict[str, Any] | None = None,
    ) -> None:
        detail = f"The {model.__name__} name {name} already exists."
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail, headers=headers)


class ResourceConflictException(HTTPException):
    """
    Generic exception for handling conflicts during operations on resources.

    :param detail: Detailed message describing the conflict.
    :param headers: Optional HTTP headers to be sent in the response.
    """

    def __init__(self, detail: str = "Resource conflict encountered.", headers: dict[str, Any] | None = None) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail, headers=headers)


class ContentNoChangeException(HTTPException):
    """
    Exception raised when an attempted update operation does not change any data.

    :param detail: Detailed message explaining no change was made.
    :param headers: Optional HTTP headers to be sent in the response.
    """

    def __init__(
        self,
        detail: str = "No changes detected in the content update.",
        headers: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail, headers=headers)


class InvalidItemAssignmentException(HTTPException, Generic[ModelType]):
    """
    Exception raised when attempting to assign an item to both a storage and a dweller.

    :param model: The model class of the item.
    :param headers: Optional HTTP headers to be sent in the response.
    """

    def __init__(
        self,
        model: type[ModelType],
        headers: dict[str, Any] | None = None,
    ) -> None:
        detail = f"The {model.__name__} cannot be assigned to both a storage and a dweller."
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail, headers=headers)


class InvalidVaultTransferException(ContentNoChangeException):
    """
    Exception raised when attempting to move an item between vaults.

    :param detail: Detailed message explaining the error.
    :param headers: Optional HTTP headers to be sent in the response.
    """

    def __init__(
        self,
        detail: str = "Items can only be moved within the same vault.",
        headers: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail=detail, headers=headers)


class VaultOperationException(HTTPException):
    """
    Base exception for errors that occur during operations within the vault.
    """

    def __init__(
        self, detail: str, headers: dict[str, Any] | None = None, status_code: int = status.HTTP_400_BAD_REQUEST
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class NoSpaceAvailableException(VaultOperationException):
    """
    Exception raised when attempting to build a room in a vault with no available space.

    :param space_needed: The amount of space needed to build the room.
    :param headers: Optional HTTP headers to be sent in the response.
    """

    def __init__(self, space_needed: int | None = None, headers: dict[str, Any] | None = None):
        detail = "No available space in vault to place the new room."
        if space_needed is not None:
            detail += f" {space_needed} units of space needed."
        super().__init__(detail=detail, headers=headers)


class InsufficientResourcesException(VaultOperationException):
    """
    Exception raised when attempting to perform an action without sufficient resources.

    :param resource_name: The name of the resource that is insufficient.
    :param resource_amount: The amount of the resource that is needed.
    :param headers: Optional HTTP headers to be sent in the response.
    """

    def __init__(
        self,
        resource_name: str | None = None,
        resource_amount: int | None = None,
        headers: dict[str, Any] | None = None,
    ):
        detail = "Insufficient resources to perform the action."
        if resource_name and resource_amount is not None:
            detail += f" Not enough {resource_name}; {resource_amount} more needed."
        super().__init__(detail=detail, headers=headers)


class UniqueRoomViolationException(VaultOperationException):
    """
    Exception raised when attempting to create a room that violates the unique room constraint.

    :param room_name: The name of room that is unique.
    :param headers: Optional HTTP headers to be sent in the response.
    """

    def __init__(self, room_name: str | None = None, headers: dict[str, Any] | None = None):
        detail = "A unique room of this type already exists in the vault."
        if room_name is not None:
            detail += f" Room name: {room_name}."
        super().__init__(detail=detail, headers=headers)


class MinioError(Exception):
    """Base class for MinIO related exceptions."""



class BucketNotFoundError(MinioError):
    """Raised when a specified bucket does not exist."""



class FileUploadError(MinioError):
    """Raised when a file upload to MinIO fails."""



class FileDownloadError(MinioError):
    """Raised when a file download from MinIO fails."""

