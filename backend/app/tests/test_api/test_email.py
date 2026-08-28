"""Tests for the superuser-only test-email endpoint (POST /email/test)."""

from unittest.mock import AsyncMock, patch

import aiosmtplib
import pytest

pytestmark = pytest.mark.asyncio


class TestTestEmailEndpoint:
    async def test_post_test_email_requires_auth(self, async_client) -> None:
        response = await async_client.post("/email/test", json={"email_to": "test@example.com"})
        assert response.status_code in (401, 403)

    async def test_post_test_email_requires_superuser(self, async_client, normal_user_token_headers) -> None:
        response = await async_client.post(
            "/email/test",
            headers=normal_user_token_headers,
            json={"email_to": "test@example.com"},
        )
        assert response.status_code == 400

    async def test_post_test_email_success(self, async_client, superuser_token_headers) -> None:
        with patch("app.services.email_service.send_email", new_callable=AsyncMock) as mock_send:
            response = await async_client.post(
                "/email/test",
                headers=superuser_token_headers,
                json={"email_to": "test@example.com"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["email_to"] == "test@example.com"
        mock_send.assert_awaited_once()

    async def test_post_test_email_smtp_failure(self, async_client, superuser_token_headers) -> None:
        with patch(
            "app.services.email_service.send_email",
            new_callable=AsyncMock,
            side_effect=aiosmtplib.SMTPException("connection refused"),
        ):
            response = await async_client.post(
                "/email/test",
                headers=superuser_token_headers,
                json={"email_to": "test@example.com"},
            )
        assert response.status_code == 502
        assert "SMTP delivery failed" in response.json()["detail"]
