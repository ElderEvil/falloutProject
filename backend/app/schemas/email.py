"""Email-related schemas (request/response models for email endpoints)."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class TestEmailRequest(BaseModel):
    """Payload for POST /email/test — send a diagnostic email via the configured SMTP server."""

    email_to: EmailStr = Field(..., max_length=320, description="Recipient address to receive the test email.")
    subject: str | None = Field(default=None, max_length=200, description="Optional override for the subject line.")
    message: str | None = Field(
        default=None, max_length=2000, description="Optional override for the body text of the test email."
    )


class TestEmailResult(BaseModel):
    """Result of a test-email attempt."""

    status: Literal["ok", "error"]
    email_to: str
    message: str | None = None
