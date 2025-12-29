"""Configuration for Locust performance tests."""

import os
from dataclasses import dataclass


@dataclass
class LocustConfig:
    """Configuration for load testing."""

    # API Configuration
    host: str = os.getenv("LOCUST_HOST", "http://localhost:8000")
    api_version: str = os.getenv("LOCUST_API_VERSION", "v1")

    # Test User Credentials
    test_user_email: str = os.getenv("LOCUST_TEST_USER_EMAIL", "test@test.com")
    test_user_password: str = os.getenv("LOCUST_TEST_USER_PASSWORD", "testpassword")
    superuser_email: str = os.getenv("LOCUST_SUPERUSER_EMAIL", "admin@admin.com")
    superuser_password: str = os.getenv("LOCUST_SUPERUSER_PASSWORD", "adminpassword")

    # Performance Thresholds
    max_response_time_ms: int = int(os.getenv("LOCUST_MAX_RESPONSE_TIME_MS", "2000"))
    percentile_95_threshold_ms: int = int(os.getenv("LOCUST_P95_THRESHOLD_MS", "1000"))

    # Test Data Configuration
    num_test_vaults: int = int(os.getenv("LOCUST_NUM_TEST_VAULTS", "10"))
    num_test_dwellers: int = int(os.getenv("LOCUST_NUM_TEST_DWELLERS", "50"))

    # Task Weights (relative probability of each action)
    weight_read_operations: int = 70  # 70% reads
    weight_write_operations: int = 20  # 20% writes
    weight_game_operations: int = 10  # 10% game ticks

    @property
    def api_base_url(self) -> str:
        """Get the full API base URL."""
        return f"{self.host}/api/{self.api_version}"


# Global config instance
config = LocustConfig()
