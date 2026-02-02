"""Storage service module with adapter pattern for MinIO and RustFS."""

from .base import StorageService
from .factory import create_storage_service, get_storage_client

__all__ = ["StorageService", "create_storage_service", "get_storage_client"]
