"""Email diagnostics endpoints (superuser-only test email)."""

from fastapi import APIRouter

from app.api.deps import CurrentSuperuser
from app.schemas.email import TestEmailRequest, TestEmailResult
from app.services.email_service import email_service

router = APIRouter(prefix="/email", tags=["email"])


@router.post("/test", response_model=TestEmailResult)
async def test_email(payload: TestEmailRequest, _: CurrentSuperuser) -> TestEmailResult:
    """Send a diagnostic email via the configured SMTP server to validate connectivity.

    Requires superuser privileges. Returns 502 if the SMTP server cannot deliver the message.
    """
    await email_service.send_test_email(
        email_to=payload.email_to,
        subject=payload.subject,
        message=payload.message,
    )
    return TestEmailResult(status="ok", email_to=payload.email_to, message="Test email sent.")
