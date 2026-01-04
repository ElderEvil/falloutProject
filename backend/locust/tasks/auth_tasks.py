"""Authentication-related tasks for load testing."""

from config import config

from locust import TaskSet, task


class AuthTaskSet(TaskSet):
    """Task set for authentication operations."""

    @task(1)
    def login_user(self):
        """Test user login."""
        self.client.post(
            "/api/v1/auth/login",
            data={
                "username": config.test_user_email,
                "password": config.test_user_password,
            },
            name="POST /auth/login",
        )

    @task(1)
    def test_token(self):
        """Test token validation."""
        if not hasattr(self.user, "access_token") or not self.user.access_token:
            return

        self.client.post(
            "/api/v1/login/test-token",
            headers=self.user.get_auth_headers(),
            name="POST /login/test-token",
        )
