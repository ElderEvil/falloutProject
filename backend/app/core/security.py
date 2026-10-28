import base64
import hashlib
import logging
import math
import secrets
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4

import jwt
from passlib.context import CryptContext
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

JWTError = jwt.InvalidTokenError


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
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token_subject(
    token: str,
    expected_type: Literal["access", "refresh", "email_verification", "password_reset"],
) -> str:
    """Verify signed, expiring credentials for exactly one purpose.

    Legacy untyped sessions are intentionally rejected. Email/reset links retain
    their existing purpose values and signing key.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub", "type"]},
        )

        expiry = payload["exp"]
        if type(expiry) not in (int, float) or (isinstance(expiry, float) and not math.isfinite(expiry)):
            raise JWTError("Invalid token expiry")
        subject = payload["sub"]
        if payload["type"] != expected_type or not isinstance(subject, str) or not subject:
            raise JWTError("Invalid token purpose or subject")
        if expected_type != "password_reset":
            UUID(subject)
    except (TypeError, ValueError, OverflowError) as exc:
        raise JWTError("Malformed token claims") from exc
    else:
        return subject


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def generate_pkce_pair() -> tuple[str, str]:
    """Return a PKCE verifier and its unpadded S256 challenge."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def hash_browser_token(value: str) -> str:
    """SHA-256 hex of a browser-binding cookie or handoff code."""
    return hashlib.sha256(value.encode()).hexdigest()


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

    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    expires_in_seconds = int(
        expires_delta.total_seconds() if expires_delta else settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60
    )

    await redis_client.setex(f"refresh_token:{subject}", expires_in_seconds, encoded_jwt)

    return encoded_jwt


async def verify_refresh_token(token: str, redis_client: Redis) -> str | None:
    try:
        subject = decode_token_subject(token, "refresh")

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
    to_encode = {"exp": expire, "sub": str(subject), "type": "email_verification", "jti": uuid4().hex}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_email_token(token: str) -> str | None:
    """
    Verify email verification token and return user ID.
    """
    try:
        return decode_token_subject(token, "email_verification")
    except JWTError:
        return None


def create_password_reset_token(subject: str | Any) -> str:
    """
    Create a token for password reset (1 hour expiry).
    """
    expire = datetime.utcnow() + timedelta(hours=1)
    to_encode = {"exp": expire, "sub": str(subject), "type": "password_reset"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_password_reset_token(token: str) -> str | None:
    """
    Verify password reset token and return user ID/email.
    """
    try:
        return decode_token_subject(token, "password_reset")
    except JWTError:
        return None
