"""Abstract base class for storage service adapters."""

from abc import abstractmethod
from typing import Protocol


class StorageService(Protocol):
    """Protocol defining the interface for storage services.

    All storage adapters (MinIO, RustFS, etc.) must implement this interface.
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
        """Upload a file to storage.

        Args:
            file_data: Raw bytes of the file
            file_name: Name/key for the file
            file_type: MIME type of the file
            bucket_name: Optional bucket name (uses default if not specified)

        Returns:
            URL or identifier of the uploaded file

        Raises:
            FileUploadError: If upload fails
        """
        ...

    @abstractmethod
    def upload_thumbnail(
        self,
        *,
        file_data: bytes,
        file_name: str,
        bucket_name: str | None = None,
    ) -> str:
        """Upload a thumbnail version of an image.

        Args:
            file_data: Raw bytes of the original image
            file_name: Name/key for the thumbnail
            bucket_name: Optional bucket name

        Returns:
            URL of the uploaded thumbnail
        """
        ...

    @abstractmethod
    def download_file(
        self,
        *,
        file_name: str,
        bucket_name: str | None = None,
    ) -> bytes:
        """Download a file from storage.

        Args:
            file_name: Name/key of the file to download
            bucket_name: Optional bucket name

        Returns:
            Raw bytes of the file

        Raises:
            FileDownloadError: If download fails
        """
        ...

    @abstractmethod
    def public_url(
        self,
        *,
        file_name: str,
        bucket_name: str | None = None,
    ) -> str:
        """Generate a public URL for accessing a file.

        Args:
            file_name: Name/key of the file
            bucket_name: Optional bucket name

        Returns:
            Publicly accessible URL
        """
        ...

    @abstractmethod
    def delete_file(
        self,
        *,
        file_name: str,
        bucket_name: str | None = None,
    ) -> bool:
        """Delete a file from storage.

        Args:
            file_name: Name/key of the file to delete
            bucket_name: Optional bucket name

        Returns:
            True if deleted successfully, False otherwise
        """
        ...

    @abstractmethod
    def file_exists(
        self,
        *,
        file_name: str,
        bucket_name: str | None = None,
    ) -> bool:
        """Check if a file exists in storage.

        Args:
            file_name: Name/key of the file
            bucket_name: Optional bucket name

        Returns:
            True if file exists, False otherwise
        """
        ...

    @abstractmethod
    def list_files(
        self,
        *,
        prefix: str = "",
        bucket_name: str | None = None,
    ) -> list[str]:
        """List files in storage with optional prefix filter.

        Args:
            prefix: Optional prefix to filter files
            bucket_name: Optional bucket name

        Returns:
            List of file names/keys
        """
        ...
