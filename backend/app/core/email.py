import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings

logger = logging.getLogger(__name__)

# SMTP exception types
SMTPExceptionTypes = (aiosmtplib.SMTPException, ConnectionError, TimeoutError, OSError)

# Setup Jinja2 for email templates
template_dir = Path(__file__).parent.parent / "templates" / "email"
jinja_env = Environment(
    loader=FileSystemLoader(str(template_dir)),
    autoescape=select_autoescape(["html", "xml"]),
)


async def send_email(
    *,
    email_to: str,
    subject: str,
    html_content: str,
    text_content: str | None = None,
) -> None:
    """
    Send an email using the configured SMTP server.

    ``text_content`` is attached as a text/plain alternative so clients that
    refuse HTML still show a readable message and spam filters see both parts.
    """
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"
    message["To"] = email_to

    if text_content:
        message.attach(MIMEText(text_content, "plain", "utf-8"))
    message.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        # Config naming is inverted vs. aiosmtplib (documented in config.py):
        # SMTP_TLS means implicit TLS (port 465), SMTP_SSL means STARTTLS (port 587).
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
            use_tls=settings.SMTP_TLS,
            start_tls=settings.SMTP_SSL,
        )
        logger.info(f"Email sent successfully to {email_to}")
    except SMTPExceptionTypes:
        logger.exception(f"Failed to send email to {email_to}")
        raise


def render_email_template(template_name: str, context: dict) -> str:
    """
    Render an email template with the given context.
    """
    template = jinja_env.get_template(template_name)
    return template.render(**context)


async def send_verification_email(*, email_to: str, username: str, token: str) -> None:
    """
    Send email verification email to user.
    """
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"

    html_content = render_email_template(
        "verify_email.html",
        {
            "username": username,
            "verification_url": verification_url,
            "project_name": settings.PROJECT_NAME,
        },
    )
    text_content = (
        f"Welcome, {username}!\n\n"
        f"Verify your {settings.PROJECT_NAME} email address by opening this link:\n"
        f"{verification_url}\n\n"
        "If you didn't create an account, you can safely ignore this email.\n"
    )

    await send_email(
        email_to=email_to,
        subject=f"{settings.PROJECT_NAME} - Verify Your Email",
        html_content=html_content,
        text_content=text_content,
    )


async def send_password_reset_email(*, email_to: str, username: str, token: str) -> None:
    """
    Send password reset email to user.
    """
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    expiry_hours = 1

    html_content = render_email_template(
        "reset_password.html",
        {
            "username": username,
            "reset_url": reset_url,
            "project_name": settings.PROJECT_NAME,
            "expiry_hours": expiry_hours,
        },
    )
    text_content = (
        f"Hello, {username}!\n\n"
        "We received a request to reset your password. Open this link to choose a new password:\n"
        f"{reset_url}\n\n"
        f"This link expires in {expiry_hours} hour(s).\n\n"
        "If you didn't request a password reset, you can safely ignore this email.\n"
    )

    await send_email(
        email_to=email_to,
        subject=f"{settings.PROJECT_NAME} - Password Reset Request",
        html_content=html_content,
        text_content=text_content,
    )


async def send_password_changed_email(*, email_to: str, username: str) -> None:
    """
    Send confirmation email after password change.
    """
    html_content = render_email_template(
        "password_changed.html",
        {
            "username": username,
            "project_name": settings.PROJECT_NAME,
            "support_email": settings.EMAIL_FROM_ADDRESS,
        },
    )
    text_content = (
        f"Hello, {username}!\n\n"
        f"Your {settings.PROJECT_NAME} password was changed successfully.\n\n"
        "If you made this change, no further action is required.\n"
        f"If you did not, contact {settings.EMAIL_FROM_ADDRESS} immediately.\n\n"
        "For your security, all active sessions have been logged out.\n"
    )

    await send_email(
        email_to=email_to,
        subject=f"{settings.PROJECT_NAME} - Password Changed",
        html_content=html_content,
        text_content=text_content,
    )
