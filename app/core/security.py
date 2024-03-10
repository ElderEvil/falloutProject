from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.db.session import async_engine

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"

UTC = timezone.utc


def create_access_token(
    subject: str | Any,
    expires_delta: timedelta = None,  # noqa: RUF013
) -> str:
    if expires_delta:
        expire = datetime.now(tz=UTC) + expires_delta
    else:
        expire = datetime.now(tz=UTC) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


async def authenticate_admin(
    email: str,
    password: str,
):
    async_session = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        user = await crud.user.authenticate(
            db_session=session,
            email=email,
            password=password,
        )
        if not user:
            raise HTTPException(status_code=400, detail="Incorrect email or password")
        if not crud.user.is_active(user):
            raise HTTPException(status_code=400, detail="Inactive user")
        return user
