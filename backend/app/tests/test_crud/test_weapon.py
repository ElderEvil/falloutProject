import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.schemas.weapon import WeaponCreate
from app.tests.factory.items import create_fake_weapon


@pytest.mark.asyncio
async def test_weapon_deletion(async_session: AsyncSession) -> None:
    weapon_data = create_fake_weapon()
    weapon_in = WeaponCreate(**weapon_data)
    weapon = await crud.weapon.create(async_session, obj_in=weapon_in)

    # Delete the weapon
    await crud.weapon.delete(async_session, id=weapon.id)

    # Try to read the deleted weapon
    with pytest.raises(HTTPException) as exc_info:
        await crud.weapon.get(async_session, id=weapon.id)
    assert exc_info.value.status_code == 404
