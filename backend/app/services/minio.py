import io
import json
import logging
from functools import lru_cache

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.utils.exceptions import BucketNotFoundError, FileDownloadError, FileUploadError
from app.utils.image_processing import generate_thumbnail

PUBLIC_POLICY_TEMPLATE = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"AWS": ["*"]},
            "Action": ["s3:GetBucketLocation", "s3:ListBucket", "s3:ListBucketMultipartUploads"],
            "Resource": [],
        },
        {
            "Effect": "Allow",
            "Principal": {"AWS": ["*"]},
            "Action": [
                "s3:AbortMultipartUpload",
                "s3:DeleteObject",
                "s3:ListMultipartUploadParts",
                "s3:PutObject",
                "s3:GetObject",
            ],
            "Resource": [],
        },
    ],
}

logger = logging.getLogger(__name__)


class MinioService:
    def __init__(self):
        self.client = None
        self.default_bucket_name = "fastapi-minio"
        self.enabled = settings.minio_enabled

        if self.enabled:
            try:
                self.client = Minio(
                    f"{settings.MINIO_HOSTNAME}:{settings.MINIO_PORT}",
                    access_key=settings.MINIO_ROOT_USER,
                    secret_key=settings.MINIO_ROOT_PASSWORD,
                    secure=False,  # Internal Docker connection is always HTTP
                )
                self._ensure_bucket_exists(self.default_bucket_name)
                logger.info("MinIO client initialized successfully")
            except (S3Error, OSError, ValueError, BucketNotFoundError) as e:
                logger.warning(f"Failed to initialize MinIO client: {e}. MinIO features will be disabled.")
                self.enabled = False
                self.client = None
        else:
            logger.info("MinIO not configured. Image/audio upload features will be disabled.")

    @staticmethod
    def _get_public_policy(bucket_name: str) -> str:
        policy = PUBLIC_POLICY_TEMPLATE.copy()
        policy["Statement"][0]["Resource"] = [f"arn:aws:s3:::{bucket_name}"]
        policy["Statement"][1]["Resource"] = [f"arn:aws:s3:::{bucket_name}/*"]
        return json.dumps(policy)

    def _ensure_bucket_exists(self, bucket_name: str) -> None:
        if not self.enabled or not self.client:
            return
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
        except S3Error as e:
            error_msg = f"Error creating bucket {bucket_name}: {e}"
            raise BucketNotFoundError(error_msg) from e

    def _ensure_bucket_policy(self, bucket_name: str) -> None:
        """
        Ensure that the bucket has the correct policy set.
        :param bucket_name: The name of the bucket to check.
        """
        if not self.enabled or not self.client:
            return
        if bucket_name not in settings.MINIO_PUBLIC_BUCKET_WHITELIST:
            return
        expected_policy = self._get_public_policy(bucket_name)
        try:
            current_policy = self.client.get_bucket_policy(bucket_name)
        except S3Error as e:
            if "NoSuchBucketPolicy" in str(e):
                current_policy = None
            else:
                error_msg = f"Error getting bucket policy for {bucket_name}: {e}"
                raise BucketNotFoundError(error_msg) from e

        if current_policy != expected_policy:
            try:
                self.client.set_bucket_policy(bucket_name, expected_policy)
            except S3Error as e:
                error_msg = f"Error setting bucket policy for {bucket_name}: {e}"
                raise BucketNotFoundError(error_msg) from e

    def upload_file(
        self, file_data: bytes, file_name: str, *, file_type: str = "image/png", bucket_name: str | None = None
    ) -> str:
        if not self.enabled or not self.client:
            logger.warning(f"MinIO disabled, skipping upload for {file_name}")
            return ""

        bucket_name = bucket_name or self.default_bucket_name
        self._ensure_bucket_exists(bucket_name)
        try:
            file_stream = io.BytesIO(file_data)
            file_size = len(file_data)
            if file_size == 0:
                err_msg = f"Attempted to upload 0-byte file: {file_name} to bucket {bucket_name}"
                logger.warning(err_msg)
                return ""
            result = self.client.put_object(
                bucket_name, file_name, file_stream, length=file_size, content_type=file_type
            )
            err_msg = f"Successfully uploaded {file_name} to {bucket_name}. ETag: {result.etag}"
            logger.info(err_msg)
            return (
                self.public_url(file_name=file_name, bucket_name=bucket_name)
                if bucket_name in settings.MINIO_PUBLIC_BUCKET_WHITELIST
                else result.object_name
            )
        except S3Error as e:
            error_msg = f"Error uploading file to MinIO: {e}"
            raise FileUploadError(error_msg) from e

    def upload_thumbnail(self, *, file_data: bytes, file_name: str, bucket_name: str | None = None) -> str:
        thumbnail_data = generate_thumbnail(file_data)
        return self.upload_file(file_data=thumbnail_data, file_name=file_name, bucket_name=bucket_name)

    def download_file(self, *, file_name: str, bucket_name: str | None = None) -> bytes:
        if not self.enabled or not self.client:
            logger.warning(f"MinIO disabled, cannot download {file_name}")
            msg = "MinIO is not available"
            raise FileDownloadError(msg)

        bucket_name = bucket_name or self.default_bucket_name
        try:
            response = self.client.get_object(bucket_name, file_name)
            return response.read()
        except S3Error as e:
            error_msg = f"Error downloading file from MinIO: {e}"
            raise FileDownloadError(error_msg) from e

    def public_url(self, *, file_name: str, bucket_name: str | None = None) -> str:
        if not self.enabled or not self.client:
            logger.warning(f"MinIO disabled, cannot generate public URL for {file_name}")
            return ""

        bucket_name = bucket_name or self.default_bucket_name
        self._ensure_bucket_policy(bucket_name)
        return f"{settings.minio_public_base_url}/{bucket_name}/{file_name}"


@lru_cache
def get_minio_client() -> MinioService:
    return MinioService()
