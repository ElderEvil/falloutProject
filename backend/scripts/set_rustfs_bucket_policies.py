# ruff: noqa: INP001
"""Set public policies on RustFS buckets."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings


def set_bucket_policies():
    """Set public read policies on all whitelisted buckets."""
    buckets = settings.RUSTFS_PUBLIC_BUCKET_WHITELIST

    client = boto3.client(
        "s3",
        endpoint_url=settings.RUSTFS_PUBLIC_URL or "https://s3-api.evillab.dev",
        aws_access_key_id=settings.RUSTFS_ACCESS_KEY or "",
        aws_secret_access_key=settings.RUSTFS_SECRET_KEY or "",
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": ["arn:aws:s3:::{bucket}/*"],
            }
        ],
    }
    serialized_policy = json.dumps(policy)

    for bucket in buckets:
        try:
            bucket_policy = serialized_policy.replace("{bucket}", bucket)
            client.put_bucket_policy(Bucket=bucket, Policy=bucket_policy)
            print(f"Set public policy for: {bucket}")
        except (BotoCoreError, ClientError) as e:
            print(f"Failed to set policy for {bucket}: {e}")


if __name__ == "__main__":
    set_bucket_policies()
