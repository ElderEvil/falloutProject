import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings

logger = logging.getLogger(__name__)

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
) -> None:
    """
    Send an email using the configured SMTP server.
    """
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"
    message["To"] = email_to

    # Attach HTML content
    html_part = MIMEText(html_content, "html")
    message.attach(html_part)

    try:
        # Connect and send email
        smtp_options = {
            "hostname": settings.SMTP_HOST,
            "port": settings.SMTP_PORT,
        }

        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            smtp_options["username"] = settings.SMTP_USER
            smtp_options["password"] = settings.SMTP_PASSWORD

        if settings.SMTP_TLS:
            smtp_options["use_tls"] = True
        elif settings.SMTP_SSL:
            smtp_options["start_tls"] = True

        await aiosmtplib.send(message, **smtp_options)
        logger.info(f"Email sent successfully to {email_to}")
    except Exception:
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

    await send_email(
        email_to=email_to,
        subject=f"{settings.PROJECT_NAME} - Verify Your Email",
        html_content=html_content,
    )


async def send_password_reset_email(*, email_to: str, username: str, token: str) -> None:
    """
    Send password reset email to user.
    """
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"

    html_content = render_email_template(
        "reset_password.html",
        {
            "username": username,
            "reset_url": reset_url,
            "project_name": settings.PROJECT_NAME,
            "expiry_hours": 1,
        },
    )

    await send_email(
        email_to=email_to,
        subject=f"{settings.PROJECT_NAME} - Password Reset Request",
        html_content=html_content,
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

    await send_email(
        email_to=email_to,
        subject=f"{settings.PROJECT_NAME} - Password Changed",
        html_content=html_content,
    )
