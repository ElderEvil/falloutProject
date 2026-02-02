#!/usr/bin/env python3
"""Archive all MinIO buckets to local filesystem."""

import os
import sys
from pathlib import Path

from minio import Minio
from minio.error import S3Error


def archive_minio(
    host: str,
    access_key: str = "minioadmin",
    secret_key: str = "minioadmin",
    output_dir: str = "./minio_archive",
    secure: bool = False,
) -> None:
    """
    Download all objects from all buckets in MinIO.

    Args:
        host: MinIO host (e.g., '192.168.88.13:9000' or 'fallout-media.evillab.dev')
        access_key: MinIO access key (default: minioadmin)
        secret_key: MinIO secret key (default: minioadmin)
        output_dir: Local directory to save files (default: ./minio_archive)
        secure: Use HTTPS instead of HTTP (default: False)
    """
    print(f"Connecting to MinIO at {host} (secure={secure})...")

    try:
        client = Minio(
            host, access_key=access_key, secret_key=secret_key, secure=secure
        )
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        sys.exit(1)

    # Create output directory
    archive_path = Path(output_dir)
    archive_path.mkdir(parents=True, exist_ok=True)
    print(f"📁 Archive directory: {archive_path.absolute()}")

    # Get list of buckets
    try:
        buckets = client.list_buckets()
    except S3Error as e:
        print(f"❌ Failed to list buckets: {e}")
        sys.exit(1)

    if not buckets:
        print("⚠️  No buckets found")
        return

    print(f"\n📦 Found {len(buckets)} bucket(s)\n")

    total_files = 0
    total_size = 0

    for bucket in buckets:
        bucket_name = bucket.name
        bucket_path = archive_path / bucket_name
        bucket_path.mkdir(exist_ok=True)

        print(f"📦 Bucket: {bucket_name}")

        try:
            objects = client.list_objects(bucket_name, recursive=True)
            bucket_files = 0
            bucket_size = 0

            for obj in objects:
                object_name = obj.object_name
                file_path = bucket_path / object_name

                # Create subdirectories if object has path separators
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # Download object
                try:
                    client.fget_object(bucket_name, object_name, str(file_path))
                    file_size = os.path.getsize(file_path)
                    bucket_files += 1
                    bucket_size += file_size
                    total_files += 1
                    total_size += file_size

                    size_mb = file_size / (1024 * 1024)
                    print(f"  ✓ {object_name} ({size_mb:.2f} MB)")

                except S3Error as e:
                    print(f"  ✗ Failed to download {object_name}: {e}")

            bucket_size_mb = bucket_size / (1024 * 1024)
            print(f"  → {bucket_files} files ({bucket_size_mb:.2f} MB)\n")

        except S3Error as e:
            print(f"  ✗ Failed to list objects: {e}\n")

    total_size_mb = total_size / (1024 * 1024)
    print("\n✅ Archive complete:")
    print(f"   Files: {total_files}")
    print(f"   Size: {total_size_mb:.2f} MB")
    print(f"   Location: {archive_path.absolute()}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Archive MinIO buckets to local filesystem"
    )
    parser.add_argument(
        "--host",
        default="192.168.88.13:9000",
        help="MinIO host:port (default: 192.168.88.13:9000)",
    )
    parser.add_argument(
        "--access-key",
        default="minioadmin",
        help="MinIO access key (default: minioadmin)",
    )
    parser.add_argument(
        "--secret-key",
        default="minioadmin",
        help="MinIO secret key (default: minioadmin)",
    )
    parser.add_argument(
        "--output",
        default="./minio_archive",
        help="Output directory (default: ./minio_archive)",
    )
    parser.add_argument(
        "--secure",
        action="store_true",
        help="Use HTTPS instead of HTTP",
    )

    args = parser.parse_args()

    archive_minio(
        host=args.host,
        access_key=args.access_key,
        secret_key=args.secret_key,
        output_dir=args.output,
        secure=args.secure,
    )
