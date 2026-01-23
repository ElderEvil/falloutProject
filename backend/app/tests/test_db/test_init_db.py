import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.db.init_db import init_db
from app.models.dweller import Dweller
from app.models.outfit import Outfit
from app.models.room import Room
from app.models.user import User
from app.models.vault import Vault
from app.models.weapon import Weapon


class TestInitDB:
    @pytest.mark.asyncio
    async def test_creates_superuser(self, async_session: AsyncSession):
        await init_db(async_session)

        user = await crud.user.get_by_email(
            email=settings.FIRST_SUPERUSER_EMAIL,
            db_session=async_session,
        )

        assert user is not None
        assert user.is_superuser is True
        assert user.username == settings.FIRST_SUPERUSER_USERNAME

    @pytest.mark.asyncio
    async def test_creates_test_user(self, async_session: AsyncSession):
        await init_db(async_session)

        user = await crud.user.get_by_email(
            email=settings.EMAIL_TEST_USER,
            db_session=async_session,
        )

        assert user is not None
        assert user.is_superuser is False
        assert user.username == "TestUser"

    @pytest.mark.asyncio
    async def test_idempotent_multiple_runs(self, async_session: AsyncSession):
        await init_db(async_session)
        await init_db(async_session)

        result = await async_session.execute(select(User))
        users = result.scalars().all()
        assert len(users) == 2

    @pytest.mark.asyncio
    async def test_creates_vault_for_test_user_only(self, async_session: AsyncSession):
        await init_db(async_session)

        test_user = await crud.user.get_by_email(
            email=settings.EMAIL_TEST_USER,
            db_session=async_session,
        )
        superuser = await crud.user.get_by_email(
            email=settings.FIRST_SUPERUSER_EMAIL,
            db_session=async_session,
        )

        test_vaults = await async_session.execute(select(Vault).where(Vault.user_id == test_user.id))
        assert len(test_vaults.scalars().all()) == 1

        super_vaults = await async_session.execute(select(Vault).where(Vault.user_id == superuser.id))
        assert len(super_vaults.scalars().all()) == 0

    @pytest.mark.asyncio
    async def test_creates_three_rooms(self, async_session: AsyncSession):
        await init_db(async_session)

        test_user = await crud.user.get_by_email(
            email=settings.EMAIL_TEST_USER,
            db_session=async_session,
        )

        rooms = await async_session.execute(select(Room).join(Vault).where(Vault.user_id == test_user.id))
        assert len(rooms.scalars().all()) == 3

    @pytest.mark.asyncio
    async def test_creates_six_dwellers(self, async_session: AsyncSession):
        await init_db(async_session)

        test_user = await crud.user.get_by_email(
            email=settings.EMAIL_TEST_USER,
            db_session=async_session,
        )

        dwellers = await async_session.execute(select(Dweller).join(Vault).where(Vault.user_id == test_user.id))
        assert len(dwellers.scalars().all()) == 6

    @pytest.mark.asyncio
    async def test_all_dwellers_have_outfits(self, async_session: AsyncSession):
        await init_db(async_session)

        test_user = await crud.user.get_by_email(
            email=settings.EMAIL_TEST_USER,
            db_session=async_session,
        )

        outfits = await async_session.execute(
            select(Outfit).join(Dweller).join(Vault).where(Vault.user_id == test_user.id)
        )
        assert len(outfits.scalars().all()) == 6

    @pytest.mark.asyncio
    async def test_all_dwellers_have_weapons(self, async_session: AsyncSession):
        await init_db(async_session)

        test_user = await crud.user.get_by_email(
            email=settings.EMAIL_TEST_USER,
            db_session=async_session,
        )

        weapons = await async_session.execute(
            select(Weapon).join(Dweller).join(Vault).where(Vault.user_id == test_user.id)
        )
        assert len(weapons.scalars().all()) == 6

    @pytest.mark.asyncio
    async def test_complete_hierarchy(self, async_session: AsyncSession):
        await init_db(async_session)

        test_user = await crud.user.get_by_email(
            email=settings.EMAIL_TEST_USER,
            db_session=async_session,
        )

        vault_result = await async_session.execute(select(Vault).where(Vault.user_id == test_user.id))
        vault = vault_result.scalar_one()

        rooms_result = await async_session.execute(select(Room).where(Room.vault_id == vault.id))
        rooms = rooms_result.scalars().all()
        assert len(rooms) == 3

        for room in rooms:
            dwellers_result = await async_session.execute(select(Dweller).where(Dweller.room_id == room.id))
            dwellers = dwellers_result.scalars().all()
            assert len(dwellers) == 2

            for dweller in dwellers:
                outfit_result = await async_session.execute(select(Outfit).where(Outfit.dweller_id == dweller.id))
                assert outfit_result.scalar_one_or_none() is not None

                weapon_result = await async_session.execute(select(Weapon).where(Weapon.dweller_id == dweller.id))
                assert weapon_result.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_dwellers_properly_assigned_to_rooms(self, async_session: AsyncSession):
        await init_db(async_session)

        test_user = await crud.user.get_by_email(
            email=settings.EMAIL_TEST_USER,
            db_session=async_session,
        )

        rooms_result = await async_session.execute(select(Room).join(Vault).where(Vault.user_id == test_user.id))
        rooms = rooms_result.scalars().all()

        for room in rooms:
            dwellers_result = await async_session.execute(select(Dweller).where(Dweller.room_id == room.id))
            dwellers = dwellers_result.scalars().all()

            assert len(dwellers) == 2
            for dweller in dwellers:
                assert dweller.room_id == room.id
                assert dweller.vault_id == room.vault_id
