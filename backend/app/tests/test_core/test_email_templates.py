"""Transactional email rendering and MIME shape.

The templates must survive clients that strip <style> blocks (Outlook's Word
engine), so layout lives in tables with inline styles and there is no
box-shadow/rgba/max-width to lose.
"""

from app.core import email as email_module

RESET_URL = "https://app.test/reset-password?token=abc123"
VERIFY_URL = "https://app.test/verify-email?token=def456"


def _assert_outlook_safe(html: str) -> None:
    assert '<table role="presentation"' in html
    assert "<style" not in html
    assert "box-shadow" not in html
    assert "rgba(" not in html
    assert "max-width" not in html


def _assert_terminal_theme(html: str) -> None:
    """Dark card with the game's green accent, set with attributes and inline styles."""
    assert 'bgcolor="#0b0f0a"' in html
    assert 'bgcolor="#101610"' in html
    assert "#00ff00" in html


def test_reset_password_template_is_table_based_and_inline_styled() -> None:
    html = email_module.render_email_template(
        "reset_password.html",
        {
            "username": "Ada",
            "reset_url": RESET_URL,
            "project_name": "Fallout Shelter",
            "expiry_hours": 1,
        },
    )

    _assert_outlook_safe(html)
    _assert_terminal_theme(html)
    assert RESET_URL in html
    assert "Reset Password" in html
    assert "expire in 1 hour" in html


def test_verify_email_template_renders_the_confirmation_link() -> None:
    html = email_module.render_email_template(
        "verify_email.html",
        {
            "username": "Ada",
            "verification_url": VERIFY_URL,
            "project_name": "Fallout Shelter",
        },
    )

    _assert_outlook_safe(html)
    _assert_terminal_theme(html)
    assert VERIFY_URL in html
    assert "Verify Email Address" in html


def test_password_changed_template_renders_the_support_address() -> None:
    html = email_module.render_email_template(
        "password_changed.html",
        {
            "username": "Ada",
            "project_name": "Fallout Shelter",
            "support_email": "support@example.test",
        },
    )

    _assert_outlook_safe(html)
    _assert_terminal_theme(html)
    assert "support@example.test" in html
    assert "Password Changed Successfully" in html


async def test_send_email_attaches_text_and_html_alternatives(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_send(message, **kwargs):
        captured["message"] = message
        captured["kwargs"] = kwargs

    monkeypatch.setattr(email_module.aiosmtplib, "send", fake_send)

    await email_module.send_email(
        email_to="ada@example.test",
        subject="Hello",
        html_content="<p>Hello</p>",
        text_content="Hello",
    )

    message = captured["message"]
    assert message.get_content_type() == "multipart/alternative"
    assert [part.get_content_type() for part in message.get_payload()] == ["text/plain", "text/html"]


async def test_send_email_without_text_keeps_the_html_only_shape(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_send(message, **kwargs):
        captured["message"] = message

    monkeypatch.setattr(email_module.aiosmtplib, "send", fake_send)

    await email_module.send_email(email_to="ada@example.test", subject="Hello", html_content="<p>Hello</p>")

    message = captured["message"]
    assert [part.get_content_type() for part in message.get_payload()] == ["text/html"]
