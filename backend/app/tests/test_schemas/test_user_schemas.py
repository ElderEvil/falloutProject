"""User schema boundaries: verification is readable, secrets never serialize."""

from app.schemas.user import UserRead, UserUpdate

SECRET_FIELDS = {
    "email_verification_token",
    "password_reset_token",
    "password_reset_expires",
}


def test_user_read_exposes_email_verified_but_no_secret_tokens() -> None:
    assert "email_verified" in UserRead.model_fields
    assert SECRET_FIELDS.isdisjoint(UserRead.model_fields)


def test_user_update_excludes_verification_and_reset_fields() -> None:
    assert "email_verified" not in UserUpdate.model_fields
    assert SECRET_FIELDS.isdisjoint(UserUpdate.model_fields)
