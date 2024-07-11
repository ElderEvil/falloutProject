import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.schemas.weapon import WeaponCreate
from app.tests.factory.items import create_fake_weapon


@pytest.mark.asyncio
async def test_create_and_read_weapon(async_session: AsyncSession) -> None:
    # Create a fake weapon
    weapon_data = create_fake_weapon()
    weapon_in = WeaponCreate(**weapon_data)
    weapon = await crud.weapon.create(async_session, obj_in=weapon_in)

    # Assertions to verify the weapon creation
    assert weapon.name == weapon_data["name"]
    assert weapon.weapon_type == weapon_data["weapon_type"]
    assert weapon.weapon_subtype == weapon_data["weapon_subtype"]

    # Read the weapon back
    weapon_read = await crud.weapon.get(async_session, id=weapon.id)
    assert weapon_read
    assert weapon.name == weapon_read.name
    assert weapon.damage_min == weapon_read.damage_min
    assert weapon.damage_max == weapon_read.damage_max


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
