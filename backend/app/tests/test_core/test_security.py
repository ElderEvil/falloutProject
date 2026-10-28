"""JWT consumers accept only signed, expiring credentials of their own purpose."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.core import security
from app.core.config import settings

PURPOSES = ("access", "refresh", "email_verification", "password_reset")


@pytest.mark.parametrize("purpose", PURPOSES)
@pytest.mark.asyncio
async def test_minted_tokens_are_exclusive_to_their_purpose(purpose, _shared_fake_redis):
    subject = str(uuid4())
    tokens = {
        "access": security.create_access_token(subject),
        "refresh": await security.create_refresh_token(subject, _shared_fake_redis),
        "email_verification": security.create_email_verification_token(subject),
        "password_reset": security.create_password_reset_token(subject),
    }
    assert security.decode_token_subject(tokens[purpose], purpose) == subject
    for other in PURPOSES:
        if other != purpose:
            with pytest.raises(security.JWTError):
                security.decode_token_subject(tokens[other], purpose)


@pytest.mark.parametrize(
    "claims",
    [
        {"exp": None},
        {"exp": []},
        {"exp": {}},
        {"exp": True},
        {"exp": "9999999999"},
        {"exp": float("nan")},
        {"exp": float("inf")},
        {"exp": 1},
        {"sub": None},
        {"sub": ""},
        {"sub": []},
        {"sub": "not-a-uuid"},
        {"type": None},
        {"type": []},
        {"type": "unknown"},
    ],
)
def test_malformed_access_claims_are_rejected(claims):
    payload = {"sub": str(uuid4()), "exp": datetime.now(UTC) + timedelta(minutes=5), "type": "access"}
    token = jwt.encode(payload | claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    with pytest.raises(security.JWTError):
        security.decode_token_subject(token, "access")


@pytest.mark.parametrize("missing", ["sub", "exp", "type"])
@pytest.mark.parametrize("purpose", PURPOSES)
def test_each_purpose_requires_all_claims(purpose, missing):
    payload = {"sub": str(uuid4()), "exp": datetime.now(UTC) + timedelta(minutes=5), "type": purpose}
    del payload[missing]
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    with pytest.raises(security.JWTError):
        security.decode_token_subject(token, purpose)


@pytest.mark.parametrize("purpose", PURPOSES)
@pytest.mark.parametrize("invalid_signature", ["wrong-key", "none"])
def test_each_purpose_verifies_signature(purpose, invalid_signature):
    payload = {"sub": str(uuid4()), "exp": datetime.now(UTC) + timedelta(minutes=5), "type": purpose}
    token = jwt.encode(
        payload,
        None if invalid_signature == "none" else "different-signing-key-at-least-32-bytes",
        algorithm="none" if invalid_signature == "none" else settings.ALGORITHM,
    )
    with pytest.raises(security.JWTError):
        security.decode_token_subject(token, purpose)


@pytest.mark.asyncio
async def test_refresh_requires_current_redis_token(_shared_fake_redis):
    subject = str(uuid4())
    token = await security.create_refresh_token(subject, _shared_fake_redis)
    assert await security.verify_refresh_token(token, _shared_fake_redis) == subject
    await security.invalidate_refresh_token(subject, _shared_fake_redis)
    assert await security.verify_refresh_token(token, _shared_fake_redis) is None


def test_existing_email_and_reset_links_keep_their_subjects():
    subject = str(uuid4())
    # Already-issued links need no new claims or signing-key rotation.
    expires = datetime.now(UTC) + timedelta(minutes=5)
    email = jwt.encode(
        {"sub": subject, "exp": expires, "type": "email_verification"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    reset = jwt.encode(
        {"sub": "player@example.com", "exp": expires, "type": "password_reset"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    assert security.verify_email_token(email) == subject
    assert security.verify_password_reset_token(reset) == "player@example.com"
    assert security.verify_email_token(reset) is None
    assert security.verify_password_reset_token(email) is None
