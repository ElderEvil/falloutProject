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
