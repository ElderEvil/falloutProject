"""Tests for RustFS storage adapter."""

# ruff: noqa: E402, ARG002, ARG005

import sys
from unittest.mock import MagicMock, patch

import pytest

sys.modules.pop("app.services.storage", None)
sys.modules.pop("app.services.storage.factory", None)

from botocore.exceptions import ClientError

from app.services.storage.rustfs_adapter import RustFSAdapter
from app.utils.exceptions import BucketNotFoundError, FileDownloadError, FileUploadError


@pytest.fixture
def mock_settings():
    """Patch settings with valid RustFS config."""
    with patch("app.services.storage.rustfs_adapter.settings") as mock:
        mock.RUSTFS_ACCESS_KEY = "test-access-key"
        mock.RUSTFS_SECRET_KEY = "test-secret-key"
        mock.RUSTFS_DEFAULT_BUCKET = "test-bucket"
        mock.RUSTFS_PUBLIC_URL = "http://rustfs.local:9000"
        mock.RUSTFS_PUBLIC_BUCKET_WHITELIST = ["test-bucket", "public-bucket"]
        yield mock


@pytest.fixture
def mock_settings_disabled():
    """Patch settings with missing RustFS config."""
    with patch("app.services.storage.rustfs_adapter.settings") as mock:
        mock.RUSTFS_ACCESS_KEY = None
        mock.RUSTFS_SECRET_KEY = None
        mock.RUSTFS_DEFAULT_BUCKET = "test-bucket"
        mock.RUSTFS_PUBLIC_URL = ""
        mock.RUSTFS_PUBLIC_BUCKET_WHITELIST = []
        yield mock


@pytest.fixture
def adapter(mock_settings):
    """Create an enabled RustFSAdapter."""
    return RustFSAdapter()


@pytest.fixture
def adapter_disabled(mock_settings_disabled):
    """Create a disabled RustFSAdapter."""
    return RustFSAdapter()


class TestInitialization:
    def test_enabled_with_valid_config(self, mock_settings):
        adapter = RustFSAdapter()
        assert adapter.enabled is True

    def test_disabled_without_access_key(self):
        with patch("app.services.storage.rustfs_adapter.settings") as mock:
            mock.RUSTFS_ACCESS_KEY = None
            mock.RUSTFS_SECRET_KEY = "test-secret-key"
            adapter = RustFSAdapter()
            assert adapter.enabled is False

    def test_disabled_without_secret_key(self):
        with patch("app.services.storage.rustfs_adapter.settings") as mock:
            mock.RUSTFS_ACCESS_KEY = "test-access-key"
            mock.RUSTFS_SECRET_KEY = None
            adapter = RustFSAdapter()
            assert adapter.enabled is False

    def test_default_bucket_name(self, mock_settings):
        adapter = RustFSAdapter()
        assert adapter.default_bucket_name == "test-bucket"


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

    def test_client_none_when_disabled(self, adapter_disabled):
        assert adapter_disabled.client is None


class TestUploadFile:
    @patch.object(RustFSAdapter, "_ensure_bucket_exists")
    def test_upload_success_public_bucket(self, mock_ensure, mock_settings):
        mock_client = MagicMock()
        with patch.object(RustFSAdapter, "client", new_callable=lambda: property(lambda self: mock_client)):
            adapter = RustFSAdapter()
            result = adapter.upload_file(b"test data", "test.txt", bucket_name="test-bucket")

            mock_client.put_object.assert_called_once()
            assert "http://rustfs.local:9000/test-bucket/test.txt" in result

    @patch.object(RustFSAdapter, "_ensure_bucket_exists")
    def test_upload_success_private_bucket(self, mock_ensure, mock_settings):
        mock_client = MagicMock()
        with patch.object(RustFSAdapter, "client", new_callable=lambda: property(lambda self: mock_client)):
            adapter = RustFSAdapter()
            result = adapter.upload_file(b"test data", "test.txt", bucket_name="private-bucket")

            mock_client.put_object.assert_called_once()
            assert result == "test.txt"

    def test_upload_disabled_returns_empty(self, adapter_disabled):
        result = adapter_disabled.upload_file(b"test data", "test.txt")
        assert result == ""

    @patch.object(RustFSAdapter, "_ensure_bucket_exists")
    def test_upload_empty_file_returns_empty(self, mock_ensure, mock_settings):
        mock_client = MagicMock()
        with patch.object(RustFSAdapter, "client", new_callable=lambda: property(lambda self: mock_client)):
            adapter = RustFSAdapter()
            result = adapter.upload_file(b"", "empty.txt")
            assert result == ""
            mock_client.put_object.assert_not_called()

    @patch.object(RustFSAdapter, "_ensure_bucket_exists")
    def test_upload_client_error_raises(self, mock_ensure, mock_settings):
        mock_client = MagicMock()
        mock_client.put_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Server error"}},
            "PutObject",
        )
        with patch.object(RustFSAdapter, "client", new_callable=lambda: property(lambda self: mock_client)):
            adapter = RustFSAdapter()
            with pytest.raises(FileUploadError):
                adapter.upload_file(b"test data", "test.txt")


class TestDownloadFile:
    def test_download_success(self, mock_settings):
        mock_client = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = b"downloaded content"
        mock_client.get_object.return_value = {"Body": mock_body}

        with patch.object(RustFSAdapter, "client", new_callable=lambda: property(lambda self: mock_client)):
            adapter = RustFSAdapter()
            result = adapter.download_file(file_name="test.txt")

            assert result == b"downloaded content"
            mock_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="test.txt")

    def test_download_disabled_raises(self, adapter_disabled):
        with pytest.raises(FileDownloadError):
            adapter_disabled.download_file(file_name="test.txt")

    def test_download_client_error_raises(self, mock_settings):
        mock_client = MagicMock()
        mock_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Key not found"}},
            "GetObject",
        )
        with patch.object(RustFSAdapter, "client", new_callable=lambda: property(lambda self: mock_client)):
            adapter = RustFSAdapter()
            with pytest.raises(FileDownloadError):
                adapter.download_file(file_name="missing.txt")


class TestPublicUrl:
    def test_public_url_with_public_url_setting(self, mock_settings):
        adapter = RustFSAdapter()
        url = adapter.public_url(file_name="image.png")
        assert url == "http://rustfs.local:9000/test-bucket/image.png"

    def test_public_url_custom_bucket(self, mock_settings):
        adapter = RustFSAdapter()
        url = adapter.public_url(file_name="doc.pdf", bucket_name="other-bucket")
        assert url == "http://rustfs.local:9000/other-bucket/doc.pdf"

    def test_public_url_disabled_returns_empty(self, adapter_disabled):
        url = adapter_disabled.public_url(file_name="test.txt")
        assert url == ""


class TestDeleteFile:
    def test_delete_success(self, mock_settings):
        mock_client = MagicMock()
        with patch.object(RustFSAdapter, "client", new_callable=lambda: property(lambda self: mock_client)):
            adapter = RustFSAdapter()
            result = adapter.delete_file(file_name="old.txt")
            assert result is True
            mock_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key="old.txt")

    def test_delete_disabled_returns_false(self, adapter_disabled):
        result = adapter_disabled.delete_file(file_name="test.txt")
        assert result is False

    def test_delete_client_error_returns_false(self, mock_settings):
        mock_client = MagicMock()
        mock_client.delete_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Denied"}},
            "DeleteObject",
        )
        with patch.object(RustFSAdapter, "client", new_callable=lambda: property(lambda self: mock_client)):
            adapter = RustFSAdapter()
            result = adapter.delete_file(file_name="test.txt")
            assert result is False


class TestFileExists:
    def test_file_exists_true(self, mock_settings):
        mock_client = MagicMock()
        with patch.object(RustFSAdapter, "client", new_callable=lambda: property(lambda self: mock_client)):
            adapter = RustFSAdapter()
            result = adapter.file_exists(file_name="exists.txt")
            assert result is True

    def test_file_exists_false(self, mock_settings):
        mock_client = MagicMock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "HeadObject",
        )
        with patch.object(RustFSAdapter, "client", new_callable=lambda: property(lambda self: mock_client)):
            adapter = RustFSAdapter()
            result = adapter.file_exists(file_name="missing.txt")
            assert result is False

    def test_file_exists_disabled_returns_false(self, adapter_disabled):
        result = adapter_disabled.file_exists(file_name="test.txt")
        assert result is False


class TestListFiles:
    def test_list_files_success(self, mock_settings):
        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "file1.txt"},
                {"Key": "file2.txt"},
                {"Key": "subdir/file3.txt"},
            ]
        }
        with patch.object(RustFSAdapter, "client", new_callable=lambda: property(lambda self: mock_client)):
            adapter = RustFSAdapter()
            result = adapter.list_files()

            assert result == ["file1.txt", "file2.txt", "subdir/file3.txt"]

    def test_list_files_with_prefix(self, mock_settings):
        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "images/photo.png"}]
        }
        with patch.object(RustFSAdapter, "client", new_callable=lambda: property(lambda self: mock_client)):
            adapter = RustFSAdapter()
            result = adapter.list_files(prefix="images/")

            mock_client.list_objects_v2.assert_called_once_with(Bucket="test-bucket", Prefix="images/")
            assert result == ["images/photo.png"]

    def test_list_files_empty_contents(self, mock_settings):
        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {}
        with patch.object(RustFSAdapter, "client", new_callable=lambda: property(lambda self: mock_client)):
            adapter = RustFSAdapter()
            result = adapter.list_files()
            assert result == []

    def test_list_files_disabled_returns_empty(self, adapter_disabled):
        result = adapter_disabled.list_files()
        assert result == []

    def test_list_files_client_error_returns_empty(self, mock_settings):
        mock_client = MagicMock()
        mock_client.list_objects_v2.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Error"}},
            "ListObjectsV2",
        )
        with patch.object(RustFSAdapter, "client", new_callable=lambda: property(lambda self: mock_client)):
            adapter = RustFSAdapter()
            result = adapter.list_files()
            assert result == []


class TestUploadThumbnail:
    @patch("app.services.storage.rustfs_adapter.generate_thumbnail")
    @patch.object(RustFSAdapter, "upload_file")
    def test_upload_thumbnail(self, mock_upload, mock_generate, mock_settings):
        mock_generate.return_value = b"thumbnail bytes"
        mock_upload.return_value = "http://rustfs.local:9000/test-bucket/thumb_test.png"

        adapter = RustFSAdapter()
        result = adapter.upload_thumbnail(file_data=b"original image", file_name="thumb_test.png")

        mock_generate.assert_called_once_with(b"original image")
        mock_upload.assert_called_once_with(
            file_data=b"thumbnail bytes",
            file_name="thumb_test.png",
            file_type="image/png",
            bucket_name=None,
        )
        assert result == "http://rustfs.local:9000/test-bucket/thumb_test.png"


class TestEnsureBucketExists:
    def test_bucket_already_exists(self, mock_settings):
        mock_client = MagicMock()
        adapter = RustFSAdapter()
        adapter._client = mock_client
        adapter._ensure_bucket_exists("test-bucket")
        mock_client.head_bucket.assert_called_once_with(Bucket="test-bucket")
        mock_client.create_bucket.assert_not_called()

    def test_bucket_created_when_missing(self, mock_settings):
        mock_client = MagicMock()
        mock_client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "HeadBucket",
        )
        adapter = RustFSAdapter()
        adapter._client = mock_client
        adapter._ensure_bucket_exists("new-bucket")
        mock_client.create_bucket.assert_called_once_with(Bucket="new-bucket")

    def test_bucket_create_error_raises(self, mock_settings):
        mock_client = MagicMock()
        mock_client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "HeadBucket",
        )
        mock_client.create_bucket.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Denied"}},
            "CreateBucket",
        )
        adapter = RustFSAdapter()
        adapter._client = mock_client
        with pytest.raises(BucketNotFoundError):
            adapter._ensure_bucket_exists("new-bucket")

    def test_bucket_check_error_raises(self, mock_settings):
        mock_client = MagicMock()
        mock_client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Internal Error"}},
            "HeadBucket",
        )
        adapter = RustFSAdapter()
        adapter._client = mock_client
        with pytest.raises(BucketNotFoundError):
            adapter._ensure_bucket_exists("test-bucket")

    def test_ensure_bucket_disabled_noop(self, adapter_disabled):
        adapter_disabled._ensure_bucket_exists("test-bucket")


class TestBucketPolicy:
    def test_is_public_bucket_true(self, mock_settings):
        adapter = RustFSAdapter()
        assert adapter._is_public_bucket("test-bucket") is True

    def test_is_public_bucket_false(self, mock_settings):
        adapter = RustFSAdapter()
        assert adapter._is_public_bucket("unknown-bucket") is False

    def test_get_public_policy(self, mock_settings):
        import json

        adapter = RustFSAdapter()
        policy_str = adapter._get_public_policy("my-bucket")
        policy = json.loads(policy_str)

        assert policy["Version"] == "2012-10-17"
        assert policy["Statement"][0]["Effect"] == "Allow"
        assert "my-bucket" in policy["Statement"][0]["Resource"][0]

    def test_ensure_bucket_policy_skips_non_public(self, mock_settings):
        mock_client = MagicMock()
        with patch.object(RustFSAdapter, "client", new_callable=lambda: property(lambda self: mock_client)):
            adapter = RustFSAdapter()
            adapter._ensure_bucket_policy("unknown-bucket")
            mock_client.put_bucket_policy.assert_not_called()
