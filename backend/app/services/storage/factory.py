"""Factory for creating storage service instances."""

import logging
from typing import Optional

from botocore.exceptions import ClientError

from .base import StorageService
from .rustfs_adapter import RustFSAdapter

logger = logging.getLogger(__name__)

_storage_client: Optional[StorageService] = None
_storage_initialized: bool = False


def create_storage_service() -> Optional[StorageService]:
    """Factory function to create the storage service.

    Returns:
        RustFS storage service instance.
        Returns None if storage is unavailable or misconfigured.
    """
    try:
        return RustFSAdapter()
    except ClientError:
        logger.exception("Failed to initialize RustFS")
        return None


def get_storage_client() -> Optional[StorageService]:
    """Get cached storage service instance.

    Unlike @lru_cache, this does NOT cache None. If initialization fails,
    subsequent calls will retry — ensuring a temporary S3 outage at startup
    doesn't permanently disable storage for the entire process lifetime.

    Returns:
        Singleton storage service instance, or None if storage is unavailable.
    """
    global _storage_client, _storage_initialized
    if not _storage_initialized:
        _storage_client = create_storage_service()
        _storage_initialized = _storage_client is not None
    return _storage_client
