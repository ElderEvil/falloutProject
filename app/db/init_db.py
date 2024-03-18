from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.user import UserCreate

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
        current_user = await crud.user.get_by_email(email=user["data"].email, db_session=db_session)

        if not current_user:
            await crud.user.create(db_session=db_session, obj_in=user["data"])
