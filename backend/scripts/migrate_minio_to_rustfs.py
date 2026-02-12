#!/usr/bin/env python3
"""Migrate data from MinIO to RustFS.

Usage:
    cd backend && uv run scripts/migrate_minio_to_rustfs.py [--dry-run] [--bucket BUCKET]

Environment variables required:
    MINIO_HOSTNAME, MINIO_PORT, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD
    RUSTFS_ACCESS_KEY, RUSTFS_SECRET_KEY, RUSTFS_PUBLIC_URL
"""

import argparse
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from minio import Minio
from minio.error import S3Error
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_minio_client() -> Minio:
    """Create MinIO client from environment variables."""
    return Minio(
        f"{os.getenv('MINIO_HOSTNAME')}:{os.getenv('MINIO_PORT')}",
        access_key=os.getenv("MINIO_ROOT_USER"),
        secret_key=os.getenv("MINIO_ROOT_PASSWORD"),
        secure=False,
    )


def get_rustfs_client() -> Any:
    """Create RustFS (S3) client from environment variables."""
    endpoint_url = os.getenv("RUSTFS_PUBLIC_URL", "https://s3.evillab.dev")
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=os.getenv("RUSTFS_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("RUSTFS_SECRET_KEY"),
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )


def migrate_object(
    minio_client: Minio,
    rustfs_client: Any,
    bucket: str,
    obj_name: str,
    dry_run: bool = False,
) -> tuple[str, bool, str]:
    """Migrate a single object from MinIO to RustFS.

    Returns:
        Tuple of (object_name, success, message)
    """
    try:
        # Download from MinIO
        response = minio_client.get_object(bucket, obj_name)
        data = response.read()
        response.close()

        if dry_run:
            return obj_name, True, f"Would migrate {len(data)} bytes"

        # Upload to RustFS
        rustfs_client.put_object(
            Bucket=bucket,
            Key=obj_name,
            Body=data,
        )

        return obj_name, True, f"Migrated {len(data)} bytes"
    except (OSError, ClientError) as e:
        return obj_name, False, str(e)


def migrate_bucket(
    minio_client: Minio,
    rustfs_client: Any,
    bucket: str,
    dry_run: bool = False,
    max_workers: int = 4,
) -> dict[str, Any]:
    """Migrate all objects in a bucket."""
    logger.info(f"Migrating bucket: {bucket}")

    # List all objects in MinIO bucket
    objects = list(minio_client.list_objects(bucket, recursive=True))
    total = len(objects)

    if total == 0:
        logger.info(f"Bucket {bucket} is empty")
        return {"total": 0, "success": 0, "failed": 0, "errors": []}

    logger.info(f"Found {total} objects in bucket {bucket}")

    # Create bucket in RustFS if it doesn't exist
    if not dry_run:
        try:
            rustfs_client.head_bucket(Bucket=bucket)
        except (OSError, ClientError, S3Error):
            logger.info(f"Creating bucket {bucket} in RustFS")
            rustfs_client.create_bucket(Bucket=bucket)

    # Migrate objects with progress bar
    success_count = 0
    failed_count = 0
    errors = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                migrate_object,
                minio_client,
                rustfs_client,
                bucket,
                obj.object_name,
                dry_run,
            ): obj.object_name
            for obj in objects
        }

        with tqdm(total=total, desc=f"Migrating {bucket}") as pbar:
            for future in as_completed(futures):
                obj_name = futures[future]
                try:
                    _, success, message = future.result()
                    if success:
                        success_count += 1
                    else:
                        failed_count += 1
                        errors.append(f"{obj_name}: {message}")
                        logger.error(f"Failed to migrate {obj_name}: {message}")
                except (OSError, ClientError) as e:
                    failed_count += 1
                    errors.append(f"{obj_name}: {e}")
                    logger.exception(f"Exception migrating {obj_name}")
                pbar.update(1)

    return {
        "total": total,
        "success": success_count,
        "failed": failed_count,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Migrate data from MinIO to RustFS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment variables required:
  MINIO_HOSTNAME, MINIO_PORT, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD
  RUSTFS_ACCESS_KEY, RUSTFS_SECRET_KEY, RUSTFS_PUBLIC_URL (optional)

Example:
  export MINIO_HOSTNAME=localhost
  export MINIO_PORT=9000
  export MINIO_ROOT_USER=admin
  export MINIO_ROOT_PASSWORD=password
  export RUSTFS_ACCESS_KEY=your-key
  export RUSTFS_SECRET_KEY=your-secret

  cd backend && uv run scripts/migrate_minio_to_rustfs.py --dry-run
  cd backend && uv run scripts/migrate_minio_to_rustfs.py --bucket my-bucket
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without actually doing it",
    )
    parser.add_argument(
        "--bucket",
        type=str,
        help="Migrate only specific bucket (default: all buckets)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )
    args = parser.parse_args()

    # Check environment variables
    required_minio = [
        "MINIO_HOSTNAME",
        "MINIO_PORT",
        "MINIO_ROOT_USER",
        "MINIO_ROOT_PASSWORD",
    ]
    required_rustfs = ["RUSTFS_ACCESS_KEY", "RUSTFS_SECRET_KEY"]

    missing = [var for var in required_minio + required_rustfs if not os.getenv(var)]
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        sys.exit(1)

    try:
        minio_client = get_minio_client()
        rustfs_client = get_rustfs_client()

        # Test connections
        logger.info("Testing MinIO connection...")
        minio_client.list_buckets()
        logger.info("MinIO connection OK")

        logger.info("Testing RustFS connection...")
        rustfs_client.list_buckets()
        logger.info("RustFS connection OK")

        # Get buckets to migrate
        buckets = [args.bucket] if args.bucket else [b.name for b in minio_client.list_buckets()]

        logger.info(f"Buckets to migrate: {buckets}")

        if args.dry_run:
            logger.info("DRY RUN MODE - No actual migration will occur")

        # Migrate each bucket
        total_stats = {"total": 0, "success": 0, "failed": 0}

        for bucket in buckets:
            stats = migrate_bucket(minio_client, rustfs_client, bucket, args.dry_run, args.workers)
            total_stats["total"] += stats["total"]
            total_stats["success"] += stats["success"]
            total_stats["failed"] += stats["failed"]

            logger.info(f"Bucket {bucket}: {stats['success']}/{stats['total']} objects migrated successfully")
            if stats["errors"]:
                logger.warning(f"Errors in {bucket}: {len(stats['errors'])} objects failed")

        # Summary
        logger.info("=" * 50)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Total objects: {total_stats['total']}")
        logger.info(f"Successful: {total_stats['success']}")
        logger.info(f"Failed: {total_stats['failed']}")

        if args.dry_run:
            logger.info("This was a dry run. No data was actually migrated.")
            logger.info("Run without --dry-run to perform actual migration.")

        sys.exit(0 if total_stats["failed"] == 0 else 1)

    except (OSError, ClientError, S3Error):
        logger.exception("Migration failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
