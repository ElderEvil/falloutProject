import io
import logging

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings
from app.utils.exceptions import BucketNotFoundError, FileDownloadError, FileUploadError
from app.utils.image_processing import generate_thumbnail

logger = logging.getLogger(__name__)


class RustFSAdapter:
    """RustFS storage adapter implementing the StorageService interface using boto3."""

    def __init__(self):
        self.client = None
        self.default_bucket_name = getattr(settings, "RUSTFS_DEFAULT_BUCKET", "fallout-shelter")
        self._enabled = self._check_enabled()

        if self._enabled:
            try:
                self.client = boto3.client(
                    "s3",
                    endpoint_url=self._get_endpoint_url(),
                    aws_access_key_id=getattr(settings, "RUSTFS_ACCESS_KEY", ""),
                    aws_secret_access_key=getattr(settings, "RUSTFS_SECRET_KEY", ""),
                    region_name="us-east-1",
                    config=Config(signature_version="s3v4"),
                )
                self._ensure_bucket_exists(self.default_bucket_name)
                logger.info("RustFS adapter initialized successfully")
            except (ClientError, OSError, ValueError, ImportError) as e:
                logger.warning(f"Failed to initialize RustFS adapter: {e}. RustFS features will be disabled.")
                self._enabled = False
                self.client = None
        else:
            logger.info("RustFS not configured. Storage features will be disabled.")

    def _check_enabled(self) -> bool:
        return all(
            [
                getattr(settings, "RUSTFS_ACCESS_KEY", None),
                getattr(settings, "RUSTFS_SECRET_KEY", None),
            ]
        )

    def _get_endpoint_url(self) -> str:
        public_url = getattr(settings, "RUSTFS_PUBLIC_URL", "")
        if public_url:
            return public_url.rstrip("/")
        hostname = getattr(settings, "RUSTFS_HOSTNAME", "s3.evillab.dev")
        port = getattr(settings, "RUSTFS_PORT", "")
        if port:
            return f"https://{hostname}:{port}"
        return f"https://{hostname}"

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _ensure_bucket_exists(self, bucket_name: str) -> None:
        if not self.enabled or not self.client:
            return
        try:
            self.client.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404":
                try:
                    self.client.create_bucket(Bucket=bucket_name)
                    logger.info(f"Created bucket: {bucket_name}")
                except ClientError as create_error:
                    error_msg = f"Error creating bucket {bucket_name}: {create_error}"
                    raise BucketNotFoundError(error_msg) from create_error
            else:
                error_msg = f"Error checking bucket {bucket_name}: {e}"
                raise BucketNotFoundError(error_msg) from e

    def _is_public_bucket(self, bucket_name: str) -> bool:
        whitelist = getattr(settings, "RUSTFS_PUBLIC_BUCKET_WHITELIST", [])
        return bucket_name in whitelist

    def upload_file(
        self,
        file_data: bytes,
        file_name: str,
        *,
        file_type: str = "image/png",
        bucket_name: str | None = None,
    ) -> str:
        if not self.enabled or not self.client:
            logger.warning(f"RustFS disabled, skipping upload for {file_name}")
            return ""

        bucket_name = bucket_name or self.default_bucket_name
        self._ensure_bucket_exists(bucket_name)

        file_size = len(file_data)
        if file_size == 0:
            err_msg = f"Attempted to upload 0-byte file: {file_name} to bucket {bucket_name}"
            logger.warning(err_msg)
            return ""

        try:
            file_stream = io.BytesIO(file_data)
            self.client.put_object(
                Bucket=bucket_name,
                Key=file_name,
                Body=file_stream,
                ContentType=file_type,
            )
            logger.info(f"Successfully uploaded {file_name} to {bucket_name}")
        except ClientError as e:
            error_msg = f"Error uploading file to RustFS: {e}"
            raise FileUploadError(error_msg) from e
        else:
            if self._is_public_bucket(bucket_name):
                return self.public_url(file_name=file_name, bucket_name=bucket_name)
            return file_name

    def upload_thumbnail(
        self,
        *,
        file_data: bytes,
        file_name: str,
        bucket_name: str | None = None,
    ) -> str:
        thumbnail_data = generate_thumbnail(file_data)
        return self.upload_file(
            file_data=thumbnail_data,
            file_name=file_name,
            file_type="image/png",
            bucket_name=bucket_name,
        )

    def download_file(
        self,
        *,
        file_name: str,
        bucket_name: str | None = None,
    ) -> bytes:
        if not self.enabled or not self.client:
            logger.warning(f"RustFS disabled, cannot download {file_name}")
            msg = "RustFS is not available"
            raise FileDownloadError(msg)

        bucket_name = bucket_name or self.default_bucket_name
        try:
            response = self.client.get_object(Bucket=bucket_name, Key=file_name)
            return response["Body"].read()
        except ClientError as e:
            error_msg = f"Error downloading file from RustFS: {e}"
            raise FileDownloadError(error_msg) from e

    def public_url(
        self,
        *,
        file_name: str,
        bucket_name: str | None = None,
    ) -> str:
        if not self.enabled:
            logger.warning(f"RustFS disabled, cannot generate public URL for {file_name}")
            return ""

        bucket_name = bucket_name or self.default_bucket_name
        base_url = self._get_endpoint_url()
        return f"{base_url}/{bucket_name}/{file_name}"

    def delete_file(
        self,
        *,
        file_name: str,
        bucket_name: str | None = None,
    ) -> bool:
        if not self.enabled or not self.client:
            logger.warning(f"RustFS disabled, cannot delete {file_name}")
            return False

        bucket_name = bucket_name or self.default_bucket_name
        try:
            self.client.delete_object(Bucket=bucket_name, Key=file_name)
            logger.info(f"Successfully deleted {file_name} from {bucket_name}")
        except ClientError:
            logger.exception("Error deleting file from RustFS")
            return False
        else:
            return True

    def file_exists(
        self,
        *,
        file_name: str,
        bucket_name: str | None = None,
    ) -> bool:
        if not self.enabled or not self.client:
            return False

        bucket_name = bucket_name or self.default_bucket_name
        try:
            self.client.head_object(Bucket=bucket_name, Key=file_name)
        except ClientError:
            return False
        else:
            return True

    def list_files(
        self,
        *,
        prefix: str = "",
        bucket_name: str | None = None,
    ) -> list[str]:
        if not self.enabled or not self.client:
            return []

        bucket_name = bucket_name or self.default_bucket_name
        try:
            response = self.client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=prefix,
            )
            contents = response.get("Contents", [])
            return [obj["Key"] for obj in contents if obj.get("Key")]
        except ClientError:
            logger.exception("Error listing files from RustFS")
            return []
