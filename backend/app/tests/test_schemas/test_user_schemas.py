"""User schema boundaries: verification is readable, secrets never serialize."""

from app.schemas.user import UserRead, UserUpdate

SECRET_FIELDS = {
    "email_verification_token",
    "password_reset_token",
    "password_reset_expires",
}


def test_user_schemas_keep_verification_readable_and_secrets_private() -> None:
    assert ("email_verified" in UserRead.model_fields, SECRET_FIELDS.isdisjoint(UserRead.model_fields)) == (True, True)
    assert ("email_verified" in UserUpdate.model_fields, SECRET_FIELDS.isdisjoint(UserUpdate.model_fields)) == (
        False,
        True,
    )
