"""Fix dweller image URLs - convert filenames to full URLs.

This script updates existing dweller records that have filenames stored
instead of full URLs, converting them to proper public URLs.
"""

import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlmodel import select

from app.core.config import settings
from app.db.session import get_async_session
from app.models.dweller import Dweller


async def fix_dweller_image_urls():
    """Update dweller image URLs from filenames to full URLs."""
    base_url = settings.RUSTFS_PUBLIC_URL or "https://s3-api.evillab.dev"
    base_url = base_url.rstrip("/")

    async for db_session in get_async_session():
        # Get all dwellers with image URLs
        result = await db_session.execute(select(Dweller).where(Dweller.image_url.is_not(None)))
        dwellers = result.scalars().all()

        updated_count = 0
        for dweller in dwellers:
            original_image = dweller.image_url
            original_thumbnail = dweller.thumbnail_url

            # Check if it's just a filename (not a full URL)
            if original_image and "://" not in original_image and not original_image.startswith("/"):
                # Convert to full URL
                dweller.image_url = f"{base_url}/dweller-images/{original_image}"
                updated_count += 1

            if original_thumbnail and "://" not in original_thumbnail and not original_thumbnail.startswith("/"):
                dweller.thumbnail_url = f"{base_url}/dweller-thumbnails/{original_thumbnail}"
                updated_count += 1

        await db_session.commit()
        print(f"Updated {updated_count} URL(s) for {len(dwellers)} dwellers")
        break


if __name__ == "__main__":
    asyncio.run(fix_dweller_image_urls())
