import io
from functools import lru_cache

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.utils.exceptions import BucketNotFoundError, FileDownloadError, FileUploadError


class MinioService:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_HOSTNAME + ":9000",
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=False,  # True if using https
        )
        self.default_bucket_name = "fastapi-minio"
        self._ensure_bucket_exists(self.default_bucket_name)

    def _ensure_bucket_exists(self, bucket_name: str) -> None:
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
        except S3Error as e:
            error_msg = f"Error creating bucket {bucket_name}: {e}"
            raise BucketNotFoundError(error_msg) from e

    def upload_file(self, *, file_data: bytes, file_name: str, bucket_name: str | None = None) -> str:
        bucket_name = bucket_name or self.default_bucket_name
        self._ensure_bucket_exists(bucket_name)
        try:
            result = self.client.put_object(
                bucket_name, file_name, io.BytesIO(file_data), length=len(file_data), content_type="image/png"
            )
        except S3Error as e:
            error_msg = f"Error uploading file to MinIO: {e}"
            raise FileUploadError(error_msg) from e
        else:
            return result.object_name

    def download_file(self, *, file_name: str, bucket_name: str | None = None) -> bytes:
        bucket_name = bucket_name or self.default_bucket_name
        try:
            response = self.client.get_object(bucket_name, file_name)
            return response.read()
        except S3Error as e:
            error_msg = f"Error downloading file from MinIO: {e}"
            raise FileDownloadError(error_msg) from e


@lru_cache
def get_minio_client() -> MinioService:
    return MinioService()
