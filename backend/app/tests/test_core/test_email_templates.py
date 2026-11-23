import pytest

from app.core import email as email_module

RESET_URL = "https://app.test/reset-password?token=abc123"
VERIFY_URL = "https://app.test/verify-email?token=def456"


def _render(template: str, context: dict) -> str:
    return email_module.render_email_template(template, context)


def _assert_outlook_safe(html: str) -> None:
    assert '<table role="presentation"' in html
    assert "<style" not in html
    assert "box-shadow" not in html
    assert "rgba(" not in html
    assert "max-width" not in html


def _assert_terminal_theme(html: str) -> None:
    # Dark card with the game's green accent, set with attributes and inline styles.
    assert 'bgcolor="#0b0f0a"' in html
    assert 'bgcolor="#101610"' in html
    assert "#00ff00" in html


@pytest.mark.parametrize(
    ("template", "context", "expected"),
    [
        (
            "reset_password.html",
            {"username": "Ada", "reset_url": RESET_URL, "project_name": "Fallout Shelter", "expiry_hours": 1},
            [RESET_URL, "Reset Password", "expire in 1 hour"],
        ),
        (
            "verify_email.html",
            {"username": "Ada", "verification_url": VERIFY_URL, "project_name": "Fallout Shelter"},
            [VERIFY_URL, "Verify Email Address"],
        ),
        (
            "password_changed.html",
            {
                "username": "Ada",
                "project_name": "Fallout Shelter",
                "support_email": "support@example.test",
            },
            ["support@example.test", "Password Changed Successfully"],
        ),
    ],
)
def test_templates_are_table_based_inline_styled_and_render_their_links(template, context, expected):
    html = _render(template, context)

    _assert_outlook_safe(html)
    _assert_terminal_theme(html)
    for text in expected:
        assert text in html


async def test_send_email_attaches_text_and_html_alternatives(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_send(message, **kwargs):
        captured["message"] = message
        captured["kwargs"] = kwargs

    monkeypatch.setattr(email_module.aiosmtplib, "send", fake_send)

    await email_module.send_email(
        email_to="ada@example.test", subject="Hello", html_content="<p>Hello</p>", text_content="Hello"
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
