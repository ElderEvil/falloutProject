"""Factory for creating storage service instances."""

import logging
from functools import lru_cache

from app.core.config import settings

from .base import StorageService
from .minio_adapter import MinIOAdapter
from .rustfs_adapter import RustFSAdapter

logger = logging.getLogger(__name__)


def create_storage_service() -> StorageService:
    """Factory function to create the appropriate storage service.

    Returns:
        StorageService implementation based on STORAGE_PROVIDER config

    Raises:
        ValueError: If STORAGE_PROVIDER is invalid
    """
    provider = getattr(settings, "STORAGE_PROVIDER", "minio").lower()

    if provider == "rustfs":
        logger.info("Using RustFS storage provider")
        return RustFSAdapter()
    if provider == "minio":
        logger.info("Using MinIO storage provider")
        return MinIOAdapter()
    error_msg = f"Invalid STORAGE_PROVIDER: {provider}. Must be 'minio' or 'rustfs'"
    raise ValueError(error_msg)


@lru_cache
def get_storage_client() -> StorageService:
    """Get cached storage service instance.

    Returns:
        Singleton storage service instance
    """
    return create_storage_service()
