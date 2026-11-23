import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.schemas.weapon import WeaponCreate
from app.tests.factory.items import create_fake_weapon
from app.utils.exceptions import ResourceNotFoundException


async def test_weapon_deletion(async_session: AsyncSession) -> None:
    weapon = await crud.weapon.create(async_session, obj_in=WeaponCreate(**create_fake_weapon()))
    await crud.weapon.delete(async_session, id=weapon.id)
    with pytest.raises(ResourceNotFoundException) as exc_info:
        await crud.weapon.get(async_session, id=weapon.id)
    assert exc_info.value.status_code == 404
