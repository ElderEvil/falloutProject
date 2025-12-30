from sqladmin.authentication import AuthenticationBackend
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.requests import Request

from app import crud
from app.db.session import async_engine


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        # Create async session
        async_session = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with async_session() as session:
            # Authenticate user
            user = await crud.user.authenticate(
                db_session=session,
                email=username,
                password=password,
            )

            # Check if user exists and is superuser
            if user and crud.user.is_superuser(user):
                # Store user ID in session
                request.session.update({"user_id": str(user.id)})
                return True

        return False

    async def logout(self, request: Request) -> bool:
        # Clear the session
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        user_id = request.session.get("user_id")

        if not user_id:
            return False

        # Create async session
        async_session = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Verify user still exists and is superuser
        async with async_session() as session:
            user = await crud.user.get(db_session=session, id=user_id)
            if user and crud.user.is_superuser(user):
                return True

        return False
