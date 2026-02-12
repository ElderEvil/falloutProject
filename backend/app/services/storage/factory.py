"""Factory for creating storage service instances."""

import logging
from functools import lru_cache
from typing import Optional

from app.core.config import settings

from .base import StorageService
from .minio_adapter import MinIOAdapter
from .rustfs_adapter import RustFSAdapter

logger = logging.getLogger(__name__)


def create_storage_service() -> Optional[StorageService]:
    """Factory function to create the appropriate storage service.

    Returns:
        StorageService implementation based on STORAGE_PROVIDER config.
        Returns None if storage is unavailable or misconfigured.
    """
    provider = getattr(settings, "STORAGE_PROVIDER", "minio").lower()

    if provider == "rustfs":
        try:
            return RustFSAdapter()
        except Exception:
            logger.exception("Failed to initialize RustFS")
            return None
    if provider == "minio":
        try:
            return MinIOAdapter()
        except Exception:
            logger.exception("Failed to initialize MinIO")
            return None
    logger.warning("Invalid STORAGE_PROVIDER: %s, no storage available", provider)
    return None


@lru_cache
def get_storage_client() -> Optional[StorageService]:
    """Get cached storage service instance.

    Returns:
        Singleton storage service instance, or None if storage is unavailable.
    """
    return create_storage_service()
