import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.dwellers import create_fake_dweller
from app.tests.factory.items import create_fake_outfit, create_fake_weapon
from app.tests.factory.rooms import create_fake_room
from app.tests.factory.vaults import create_fake_vault

logger = logging.getLogger(__name__)

users: list[dict[str, str | UserCreate]] = [
    {
        "data": UserCreate(
            username=settings.FIRST_SUPERUSER_USERNAME,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            email=settings.FIRST_SUPERUSER_EMAIL,
            is_superuser=True,
        ),
    },
    {
        "data": UserCreate(
            username="TestUser",
            password="testpassword",  # noqa: S106
            email=settings.EMAIL_TEST_USER,
        ),
    },
]


async def init_db(db_session: AsyncSession) -> None:
    for user in users:
        existing_user = await crud.user.get_by_email(email=user["data"].email, db_session=db_session)

        if not existing_user:
            new_user = await crud.user.create(db_session=db_session, obj_in=user["data"])
            if new_user.email == settings.EMAIL_TEST_USER:
                for _ in range(3):
                    vault_data = create_fake_vault()
                    vault_in = VaultCreateWithUserID(**vault_data, user_id=new_user.id)
                    vault = await crud.vault.create(db_session, obj_in=vault_in)
                    logger.debug(f"Vault created: {vault.name}")
                    for _ in range(3):
                        room_data = create_fake_room()
                        room_data.update({"vault_id": str(vault.id)})
                        room = await crud.room.create(db_session, obj_in=room_data)
                        logger.debug(f"Room created: {room.name}")
                        for _ in range(3):
                            dweller_data = create_fake_dweller()
                            dweller_data.update({"vault_id": str(vault.id), "room_id": str(room.id)})
                            dweller = await crud.dweller.create(db_session, obj_in=dweller_data)
                            logger.debug(f"Dweller created: {dweller.first_name} {dweller.last_name}")
                            outfit_data = create_fake_outfit()
                            outfit_data.update({"dweller_id": str(dweller.id)})
                            await crud.outfit.create(db_session, obj_in=outfit_data)
                            logger.debug(f"Outfit created: {outfit_data['name']}")
                            weapon_data = create_fake_weapon()
                            weapon_data.update({"dweller_id": str(dweller.id)})
                            await crud.weapon.create(db_session, obj_in=weapon_data)
                            logger.debug(f"Weapon created: {weapon_data['name']}")
