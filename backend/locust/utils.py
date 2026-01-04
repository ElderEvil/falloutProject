"""Utility functions for Locust tests."""

import random
from typing import Any

from locust import HttpUser


class AuthMixin:
    """Mixin to handle authentication for Locust users."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.access_token: str | None = None
        self.vault_ids: list[str] = []
        self.dweller_ids: list[str] = []

    def login(self: HttpUser, email: str, password: str) -> dict[str, Any]:
        """
        Login and store access token.

        Args:
            email: User email
            password: User password

        Returns:
            Login response data
        """
        with self.client.post(
            "/api/v1/login/access-token",
            data={"username": email, "password": password},
            name="Login",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                response.success()
                return data
            # Add more detail to the failure message
            try:
                error_detail = response.json().get("detail", "Unknown error")
            except (ValueError, KeyError):
                error_detail = response.text
            response.failure(f"Login failed {response.status_code}: {error_detail} (user: {email})")
            return {}

    def get_auth_headers(self: HttpUser) -> dict[str, str]:
        """Get authorization headers with current token."""
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    def authenticated_get(self: HttpUser, url: str, **kwargs) -> Any:
        """Make authenticated GET request."""
        headers = kwargs.pop("headers", {})
        headers.update(self.get_auth_headers())
        return self.client.get(url, headers=headers, **kwargs)

    def authenticated_post(self: HttpUser, url: str, **kwargs) -> Any:
        """Make authenticated POST request."""
        headers = kwargs.pop("headers", {})
        headers.update(self.get_auth_headers())
        return self.client.post(url, headers=headers, **kwargs)

    def authenticated_put(self: HttpUser, url: str, **kwargs) -> Any:
        """Make authenticated PUT request."""
        headers = kwargs.pop("headers", {})
        headers.update(self.get_auth_headers())
        return self.client.put(url, headers=headers, **kwargs)

    def authenticated_delete(self: HttpUser, url: str, **kwargs) -> Any:
        """Make authenticated DELETE request."""
        headers = kwargs.pop("headers", {})
        headers.update(self.get_auth_headers())
        return self.client.delete(url, headers=headers, **kwargs)


def generate_vault_number() -> int:
    """Generate a random vault number between 1 and 999."""
    return random.randint(1, 999)


def generate_dweller_name() -> str:
    """Generate a random dweller name."""
    first_names = [
        "John",
        "Jane",
        "Mike",
        "Sarah",
        "Tom",
        "Lisa",
        "Bob",
        "Alice",
        "Charlie",
        "Emma",
    ]
    last_names = [
        "Smith",
        "Johnson",
        "Williams",
        "Brown",
        "Jones",
        "Garcia",
        "Miller",
        "Davis",
        "Rodriguez",
        "Martinez",
    ]
    return f"{random.choice(first_names)} {random.choice(last_names)}"


def pick_random(items: list) -> Any:
    """Pick a random item from a list, return None if empty."""
    return random.choice(items) if items else None
