"""NoOp (no-operation) storage adapter for when storage is unavailable."""

import logging
from typing import Protocol

from app.utils.exceptions import FileDownloadError

logger = logging.getLogger(__name__)


class NoOpStorageAdapter(Protocol):
    """NoOp storage adapter that does nothing when storage is unavailable."""

    @property
    def enabled(self) -> bool:
        """Always returns False since storage is not available."""
        return False

    def upload_file(
        self,
        _file_data: bytes,
        file_name: str,
        *,
        _file_type: str = "image/png",
        _bucket_name: str | None = None,
    ) -> str:
        """No-op upload - logs warning and returns empty string."""
        logger.warning("Storage disabled, skipping upload for %s", file_name)
        return ""

    def upload_thumbnail(
        self,
        *,
        _file_data: bytes,
        file_name: str,
        _bucket_name: str | None = None,
    ) -> str:
        """No-op thumbnail upload - logs warning and returns empty string."""
        logger.warning("Storage disabled, skipping thumbnail upload for %s", file_name)
        return ""

    def download_file(
        self,
        *,
        file_name: str,
        _bucket_name: str | None = None,
    ) -> bytes:
        """No-op download - logs warning and raises error."""
        logger.warning("Storage disabled, cannot download %s", file_name)
        msg = "Storage is not available"
        raise FileDownloadError(msg)

    def public_url(
        self,
        *,
        file_name: str,
        _bucket_name: str | None = None,
    ) -> str:
        """No-op URL generation - logs warning and returns empty string."""
        logger.warning("Storage disabled, cannot generate public URL for %s", file_name)
        return ""

    def delete_file(
        self,
        *,
        file_name: str,
        _bucket_name: str | None = None,
    ) -> bool:
        """No-op delete - logs warning and returns False."""
        logger.warning("Storage disabled, cannot delete %s", file_name)
        return False

    def file_exists(
        self,
        *,
        _file_name: str,
        _bucket_name: str | None = None,
    ) -> bool:
        """No-op check - always returns False."""
        return False

    def list_files(
        self,
        *,
        _prefix: str = "",
        _bucket_name: str | None = None,
    ) -> list[str]:
        """No-op list - always returns empty list."""
        return []
