import logging
from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(
    subject: str | Any,
    expires_delta: timedelta | None = None,
) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


async def create_refresh_token(
    subject: Any,
    redis_client: Redis,
    expires_delta: timedelta | None = None,
) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    expires_in_seconds = int(
        expires_delta.total_seconds() if expires_delta else settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60
    )

    await redis_client.setex(f"refresh_token:{subject}", expires_in_seconds, encoded_jwt)

    return encoded_jwt


async def verify_refresh_token(token: str, redis_client: Redis) -> Any:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        subject = payload.get("sub")

        stored_refresh_token = await redis_client.get(f"refresh_token:{subject}")
        if stored_refresh_token != token:
            return None
    except JWTError:
        return None
    else:
        return subject


async def invalidate_refresh_token(subject: str, redis_client: Redis) -> None:
    logger.info("Invalidating refresh token for subject")
    await redis_client.delete(f"refresh_token:{subject}")


def create_email_verification_token(subject: str | Any) -> str:
    """
    Create a token for email verification (7 day expiry).
    """
    expire = datetime.utcnow() + timedelta(days=7)
    to_encode = {"exp": expire, "sub": str(subject), "type": "email_verification"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_email_token(token: str) -> Any:
    """
    Verify email verification token and return user ID.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "email_verification":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def create_password_reset_token(subject: str | Any) -> str:
    """
    Create a token for password reset (1 hour expiry).
    """
    expire = datetime.utcnow() + timedelta(hours=1)
    to_encode = {"exp": expire, "sub": str(subject), "type": "password_reset"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_password_reset_token(token: str) -> Any:
    """
    Verify password reset token and return user ID/email.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "password_reset":
            return None
        return payload.get("sub")
    except JWTError:
        return None
