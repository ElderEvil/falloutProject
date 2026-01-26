"""Quick script to check if rooms have image URLs."""

import asyncio

from sqlmodel import select

from app.db.session import async_engine
from app.models.room import Room


async def check_rooms():
    """Check first 10 rooms for image URLs."""
    from sqlmodel.ext.asyncio.session import AsyncSession

    async with AsyncSession(async_engine) as session:
        result = await session.exec(select(Room).limit(10))
        rooms = result.all()

        print("\n" + "=" * 80)
        print("ROOM IMAGE URL CHECK")
        print("=" * 80)

        for room in rooms:
            size = room.size if room.size is not None else room.size_min
            print(f"\n{room.name}")
            print(f"  Tier: {room.tier}")
            print(f"  Size: {size}")
            print(f"  Image URL: {room.image_url or 'NO IMAGE URL'}")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(check_rooms())
