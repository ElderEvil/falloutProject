"""Set public policies on RustFS buckets."""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import boto3
from botocore.config import Config
from app.core.config import settings


async def set_bucket_policies():
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

    for bucket in buckets:
        try:
            bucket_policy = json.dumps(policy).replace("{bucket}", bucket)
            client.put_bucket_policy(Bucket=bucket, Policy=bucket_policy)
            print(f"✅ Set public policy for: {bucket}")
        except Exception as e:
            print(f"❌ Failed to set policy for {bucket}: {e}")


if __name__ == "__main__":
    asyncio.run(set_bucket_policies())
