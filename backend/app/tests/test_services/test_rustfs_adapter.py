import json
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.modules.pop("app.services.storage", None)
sys.modules.pop("app.services.storage.factory", None)

from botocore.exceptions import ClientError

from app.services.storage.rustfs_adapter import RustFSAdapter
from app.utils.exceptions import BucketNotFoundError, FileDownloadError, FileUploadError

PUBLIC_URL = "http://rustfs.local:9000"


@pytest.fixture
def mock_settings():
    with patch("app.services.storage.rustfs_adapter.settings") as mock:
        mock.RUSTFS_ACCESS_KEY = "test-access-key"
        mock.RUSTFS_SECRET_KEY = "test-secret-key"
        mock.RUSTFS_DEFAULT_BUCKET = "test-bucket"
        mock.RUSTFS_PUBLIC_URL = PUBLIC_URL
        mock.RUSTFS_PUBLIC_BUCKET_WHITELIST = ["test-bucket", "public-bucket"]
        yield mock


@pytest.fixture
def mock_settings_disabled():
    with patch("app.services.storage.rustfs_adapter.settings") as mock:
        mock.RUSTFS_ACCESS_KEY = None
        mock.RUSTFS_SECRET_KEY = None
        mock.RUSTFS_DEFAULT_BUCKET = "test-bucket"
        mock.RUSTFS_PUBLIC_URL = ""
        mock.RUSTFS_PUBLIC_BUCKET_WHITELIST = []
        yield mock


@pytest.fixture
def adapter_disabled(mock_settings_disabled):
    return RustFSAdapter()


@pytest.fixture
def client_adapter(mock_settings):
    """An adapter whose ``client`` property yields one shared MagicMock."""
    mock = MagicMock()
    with patch.object(RustFSAdapter, "client", new_callable=lambda: property(lambda self: mock)):
        yield RustFSAdapter(), mock


def _error(code: str, message: str, operation: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message}}, operation)


class TestClientLazyInit:
    @patch("app.services.storage.rustfs_adapter.boto3")
    def test_client_created_on_first_access(self, mock_boto3, mock_settings):
        adapter = RustFSAdapter()
        mock_boto3.client.return_value = MagicMock()
        _ = adapter.client
        mock_boto3.client.assert_called_once()
        call_kwargs = mock_boto3.client.call_args
        assert call_kwargs[0][0] == "s3"
        assert call_kwargs[1]["aws_access_key_id"] == "test-access-key"
        assert call_kwargs[1]["aws_secret_access_key"] == "test-secret-key"


class TestUploadFile:
    @patch.object(RustFSAdapter, "_ensure_bucket_exists")
    def test_upload_success_public_bucket(self, mock_ensure, client_adapter):
        adapter, mock_client = client_adapter
        result = adapter.upload_file(b"test data", "test.txt", bucket_name="test-bucket")
        mock_client.put_object.assert_called_once()
        assert f"{PUBLIC_URL}/test-bucket/test.txt" in result

    @patch.object(RustFSAdapter, "_ensure_bucket_exists")
    def test_upload_success_private_bucket(self, mock_ensure, client_adapter):
        adapter, mock_client = client_adapter
        result = adapter.upload_file(b"test data", "test.txt", bucket_name="private-bucket")
        mock_client.put_object.assert_called_once()
        assert result == "test.txt"

    def test_upload_disabled_returns_empty(self, adapter_disabled):
        assert adapter_disabled.upload_file(b"test data", "test.txt") == ""

    @patch.object(RustFSAdapter, "_ensure_bucket_exists")
    def test_upload_empty_file_returns_empty(self, mock_ensure, client_adapter):
        adapter, mock_client = client_adapter
        assert adapter.upload_file(b"", "empty.txt") == ""
        mock_client.put_object.assert_not_called()

    @patch.object(RustFSAdapter, "_ensure_bucket_exists")
    def test_upload_client_error_raises(self, mock_ensure, client_adapter):
        adapter, mock_client = client_adapter
        mock_client.put_object.side_effect = _error("InternalError", "Server error", "PutObject")
        with pytest.raises(FileUploadError):
            adapter.upload_file(b"test data", "test.txt")


class TestDownloadFile:
    def test_download_success(self, client_adapter):
        adapter, mock_client = client_adapter
        mock_body = MagicMock()
        mock_body.read.return_value = b"downloaded content"
        mock_client.get_object.return_value = {"Body": mock_body}
        assert adapter.download_file(file_name="test.txt") == b"downloaded content"
        mock_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="test.txt")

    def test_download_disabled_raises(self, adapter_disabled):
        with pytest.raises(FileDownloadError):
            adapter_disabled.download_file(file_name="test.txt")

    def test_download_client_error_raises(self, client_adapter):
        adapter, mock_client = client_adapter
        mock_client.get_object.side_effect = _error("NoSuchKey", "Key not found", "GetObject")
        with pytest.raises(FileDownloadError):
            adapter.download_file(file_name="missing.txt")


class TestPublicUrl:
    def test_public_url_disabled_returns_empty(self, adapter_disabled):
        assert adapter_disabled.public_url(file_name="test.txt") == ""


class TestDeleteFile:
    def test_delete_success(self, client_adapter):
        adapter, mock_client = client_adapter
        assert adapter.delete_file(file_name="old.txt") is True
        mock_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key="old.txt")

    def test_delete_disabled_returns_false(self, adapter_disabled):
        assert adapter_disabled.delete_file(file_name="test.txt") is False

    def test_delete_client_error_returns_false(self, client_adapter):
        adapter, mock_client = client_adapter
        mock_client.delete_object.side_effect = _error("AccessDenied", "Denied", "DeleteObject")
        assert adapter.delete_file(file_name="test.txt") is False


class TestFileExists:
    def test_file_exists_true(self, client_adapter):
        adapter, _mock_client = client_adapter
        assert adapter.file_exists(file_name="exists.txt") is True

    def test_file_exists_false(self, client_adapter):
        adapter, mock_client = client_adapter
        mock_client.head_object.side_effect = _error("404", "Not Found", "HeadObject")
        assert adapter.file_exists(file_name="missing.txt") is False

    def test_file_exists_disabled_returns_false(self, adapter_disabled):
        assert adapter_disabled.file_exists(file_name="test.txt") is False


class TestListFiles:
    def test_list_files_with_prefix(self, client_adapter):
        adapter, mock_client = client_adapter
        mock_client.list_objects_v2.return_value = {"Contents": [{"Key": "images/photo.png"}]}
        result = adapter.list_files(prefix="images/")
        mock_client.list_objects_v2.assert_called_once_with(Bucket="test-bucket", Prefix="images/")
        assert result == ["images/photo.png"]

    def test_list_files_disabled_returns_empty(self, adapter_disabled):
        assert adapter_disabled.list_files() == []

    def test_list_files_client_error_returns_empty(self, client_adapter):
        adapter, mock_client = client_adapter
        mock_client.list_objects_v2.side_effect = _error("InternalError", "Error", "ListObjectsV2")
        assert adapter.list_files() == []


class TestUploadThumbnail:
    @patch("app.services.storage.rustfs_adapter.generate_thumbnail")
    @patch.object(RustFSAdapter, "upload_file")
    def test_upload_thumbnail(self, mock_upload, mock_generate, mock_settings):
        mock_generate.return_value = b"thumbnail bytes"
        mock_upload.return_value = f"{PUBLIC_URL}/test-bucket/thumb_test.png"
        result = RustFSAdapter().upload_thumbnail(file_data=b"original image", file_name="thumb_test.png")
        mock_generate.assert_called_once_with(b"original image")
        mock_upload.assert_called_once_with(
            file_data=b"thumbnail bytes", file_name="thumb_test.png", file_type="image/png", bucket_name=None
        )
        assert result == f"{PUBLIC_URL}/test-bucket/thumb_test.png"


class TestEnsureBucketExists:
    def test_bucket_created_when_missing(self, mock_settings):
        mock_client = MagicMock()
        mock_client.head_bucket.side_effect = _error("404", "Not Found", "HeadBucket")
        adapter = RustFSAdapter()
        adapter._client = mock_client
        adapter._ensure_bucket_exists("new-bucket")
        mock_client.create_bucket.assert_called_once_with(Bucket="new-bucket")

    def test_bucket_create_error_raises(self, mock_settings):
        mock_client = MagicMock()
        mock_client.head_bucket.side_effect = _error("404", "Not Found", "HeadBucket")
        mock_client.create_bucket.side_effect = _error("AccessDenied", "Denied", "CreateBucket")
        adapter = RustFSAdapter()
        adapter._client = mock_client
        with pytest.raises(BucketNotFoundError):
            adapter._ensure_bucket_exists("new-bucket")

    def test_bucket_check_error_raises(self, mock_settings):
        mock_client = MagicMock()
        mock_client.head_bucket.side_effect = _error("500", "Internal Error", "HeadBucket")
        adapter = RustFSAdapter()
        adapter._client = mock_client
        with pytest.raises(BucketNotFoundError):
            adapter._ensure_bucket_exists("test-bucket")

    def test_ensure_bucket_disabled_noop(self, adapter_disabled):
        adapter_disabled._ensure_bucket_exists("test-bucket")


class TestBucketPolicy:
    def test_get_public_policy(self, mock_settings):
        policy = json.loads(RustFSAdapter()._get_public_policy("my-bucket"))
        assert policy["Version"] == "2012-10-17"
        assert policy["Statement"][0]["Effect"] == "Allow"
        assert "my-bucket" in policy["Statement"][0]["Resource"][0]
