"""Abstract base class for storage service adapters."""

from abc import abstractmethod
from typing import Protocol


class StorageService(Protocol):
    """Protocol defining the interface for storage services.

    All storage adapters (RustFS, etc.) must implement this interface.
    """

    @property
    def enabled(self) -> bool:
        """Check if the storage service is enabled and configured."""
        ...

    @abstractmethod
    def upload_file(
        self,
        file_data: bytes,
        file_name: str,
        *,
        file_type: str = "image/png",
        bucket_name: str | None = None,
    ) -> str:
        """Upload a file to storage."""
        ...

    @abstractmethod
    def upload_thumbnail(
        self,
        *,
        file_data: bytes,
        file_name: str,
        bucket_name: str | None = None,
    ) -> str:
        """Upload a thumbnail version of an image."""
        ...

    @abstractmethod
    def download_file(
        self,
        *,
        file_name: str,
        bucket_name: str | None = None,
    ) -> bytes:
        """Download a file from storage."""
        ...

    @abstractmethod
    def public_url(
        self,
        *,
        file_name: str,
        bucket_name: str | None = None,
    ) -> str:
        """Generate a public URL for accessing a file."""
        ...

    @abstractmethod
    def delete_file(
        self,
        *,
        file_name: str,
        bucket_name: str | None = None,
    ) -> bool:
        """Delete a file from storage."""
        ...

    @abstractmethod
    def file_exists(
        self,
        *,
        file_name: str,
        bucket_name: str | None = None,
    ) -> bool:
        """Check if a file exists in storage."""
        ...

    @abstractmethod
    def list_files(
        self,
        *,
        prefix: str = "",
        bucket_name: str | None = None,
    ) -> list[str]:
        """List files in storage with optional prefix filter."""
        ...
