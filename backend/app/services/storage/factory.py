"""Factory for creating storage service instances."""

import logging
from functools import lru_cache

from app.core.config import settings

from .base import StorageService
from .minio_adapter import MinIOAdapter
from .noop_adapter import NoOpStorageAdapter
from .rustfs_adapter import RustFSAdapter

logger = logging.getLogger(__name__)


class _NoOpStorageSingleton:
    """Singleton instance of NoOpStorageAdapter."""

    _instance: StorageService | None = None

    @classmethod
    def get(cls) -> StorageService:
        """Get or create the singleton NoOp storage instance."""
        if cls._instance is None:
            cls._instance = NoOpStorageAdapter()
        return cls._instance


def create_storage_service() -> StorageService:
    """Factory function to create the appropriate storage service.

    Returns:
        StorageService implementation based on STORAGE_PROVIDER config.
        Returns NoOpStorageAdapter if storage is unavailable or misconfigured.
    """
    provider = getattr(settings, "STORAGE_PROVIDER", "minio").lower()

    if provider == "rustfs":
        logger.info("Using RustFS storage provider")
        try:
            return RustFSAdapter()
        except Exception:
            logger.exception("Failed to initialize RustFS, falling back to NoOp")
            return _NoOpStorageSingleton.get()
    if provider == "minio":
        logger.info("Using MinIO storage provider")
        try:
            return MinIOAdapter()
        except Exception:
            logger.exception("Failed to initialize MinIO, falling back to NoOp")
            return _NoOpStorageSingleton.get()
    logger.warning("Invalid STORAGE_PROVIDER: %s, using NoOp", provider)
    return _NoOpStorageSingleton.get()


@lru_cache
def get_storage_client() -> StorageService:
    """Get cached storage service instance.

    Returns:
        Singleton storage service instance
    """
    return create_storage_service()
