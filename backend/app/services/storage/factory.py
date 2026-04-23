"""Factory for creating storage service instances."""

import logging
from functools import lru_cache
from typing import Optional

from .base import StorageService
from .rustfs_adapter import RustFSAdapter

logger = logging.getLogger(__name__)


def create_storage_service() -> Optional[StorageService]:
    """Factory function to create the storage service.

    Returns:
        RustFS storage service instance.
        Returns None if storage is unavailable or misconfigured.
    """
    try:
        return RustFSAdapter()
    except Exception:
        logger.exception("Failed to initialize RustFS")
        return None


@lru_cache
def get_storage_client() -> Optional[StorageService]:
    """Get cached storage service instance.

    Returns:
        Singleton storage service instance, or None if storage is unavailable.
    """
    return create_storage_service()
