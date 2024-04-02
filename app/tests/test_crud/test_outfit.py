import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.schemas.outfit import OutfitCreate
from app.tests.factory.items import create_fake_outfit


@pytest.mark.asyncio
async def test_create_and_read_outfit(async_session: AsyncSession) -> None:
    # Create a fake outfit
    outfit_data = create_fake_outfit()
    outfit_in = OutfitCreate(**outfit_data)
    outfit = await crud.outfit.create(async_session, obj_in=outfit_in)

    # Assertions to verify the outfit creation
    assert outfit.name == outfit_data["name"]
    assert outfit.outfit_type == outfit_data["outfit_type"]
    assert outfit.gender == outfit_data["gender"]

    # Read the outfit back
    outfit_read = await crud.outfit.get(async_session, id=outfit.id)
    assert outfit_read
    assert outfit.name == outfit_read.name


@pytest.mark.asyncio
async def test_outfit_deletion(async_session: AsyncSession) -> None:
    outfit_data = create_fake_outfit()
    outfit_in = OutfitCreate(**outfit_data)
    outfit = await crud.outfit.create(async_session, obj_in=outfit_in)

    # Delete the outfit
    await crud.outfit.delete(async_session, id=outfit.id)

    # Try to read the deleted outfit
    with pytest.raises(HTTPException) as exc_info:
        await crud.outfit.get(async_session, id=outfit.id)
    assert exc_info.value.status_code == 404
