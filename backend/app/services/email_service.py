"""Email delivery service (business logic for outbound email)."""

import logging

from app.core.config import settings
from app.core.email import SMTPExceptionTypes, render_email_template, send_email
from app.utils.exceptions import EmailDeliveryException

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending outbound emails via the configured SMTP server."""

    async def send_test_email(self, *, email_to: str, subject: str | None = None, message: str | None = None) -> None:
        """Send a diagnostic email through the configured SMTP server.

        Raises EmailDeliveryException (HTTP 502) if the SMTP server cannot be reached
        or rejects the message, so the caller can surface the failure to the client.
        """
        html_content = render_email_template(
            "test_email.html",
            {
                "project_name": settings.PROJECT_NAME,
                "smtp_host": settings.SMTP_HOST,
                "smtp_port": settings.SMTP_PORT,
                "message": message or "This is a test email sent from the vault control panel.",
            },
        )

        try:
            await send_email(
                email_to=email_to,
                subject=subject or f"{settings.PROJECT_NAME} - Test Email",
                html_content=html_content,
            )
        except SMTPExceptionTypes as exc:
            logger.exception(f"Test email to {email_to} failed")
            raise EmailDeliveryException(detail=f"SMTP delivery failed: {exc}") from exc


email_service = EmailService()
