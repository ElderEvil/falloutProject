from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings

_BUDGET_FIELDS = (
    "POSTGRES_MAX_CONNECTIONS",
    "POSTGRES_RESERVED_CONNECTIONS",
    "WEB_CONCURRENCY",
    "API_DB_POOL_SIZE",
    "API_DB_MAX_OVERFLOW",
    "DRAMATIQ_PROCESSES",
    "DRAMATIQ_THREADS",
    "TASK_DB_POOL_SIZE",
    "TASK_DB_MAX_OVERFLOW",
    "NOTIFICATION_READ_RETENTION_DAYS",
    "NOTIFICATION_UNREAD_RETENTION_DAYS",
)

# Supplied explicitly so the assertions do not depend on a developer's .env.
_REQUIRED_SETTINGS: dict[str, Any] = {
    "ENVIRONMENT": "local",
    "SECRET_KEY": "test-secret",
    "EMAIL_TEST_USER": "test@example.com",
    "FIRST_SUPERUSER_USERNAME": "admin",
    "FIRST_SUPERUSER_EMAIL": "admin@example.com",
    "FIRST_SUPERUSER_PASSWORD": "test-password",
    "USERS_OPEN_REGISTRATION": False,
    "POSTGRES_SERVER": "localhost",
    "POSTGRES_USER": "postgres",
    "POSTGRES_PASSWORD": "postgres",
    "POSTGRES_DB": "fallout_db",
    "REDIS_HOST": "localhost",
    "REDIS_PORT": "6379",
}


def _settings_with_documented_defaults(**overrides: Any) -> Settings:
    defaults = {name: Settings.model_fields[name].default for name in _BUDGET_FIELDS}
    return Settings(_env_file=None, **{**_REQUIRED_SETTINGS, **defaults, **overrides})


def test_default_connection_budget_keeps_headroom() -> None:
    settings = _settings_with_documented_defaults()

    assert settings.api_pool_connections == 15
    assert settings.task_pool_connections == 32
    assert settings.peak_database_connections == 50
    assert settings.POSTGRES_MAX_CONNECTIONS - settings.peak_database_connections == 50


def test_worker_process_increase_is_rejected() -> None:
    with pytest.raises(ValidationError, match="connection budget"):
        _settings_with_documented_defaults(DRAMATIQ_PROCESSES=6)


def test_api_process_increase_is_rejected() -> None:
    with pytest.raises(ValidationError, match="connection budget"):
        _settings_with_documented_defaults(WEB_CONCURRENCY=5)


def test_peak_equal_to_limit_is_rejected() -> None:
    with pytest.raises(ValidationError, match="connection budget"):
        _settings_with_documented_defaults(POSTGRES_MAX_CONNECTIONS=50)


def test_peak_one_below_limit_is_accepted() -> None:
    settings = _settings_with_documented_defaults(POSTGRES_MAX_CONNECTIONS=51)

    assert settings.peak_database_connections == 50


def test_unread_notification_retention_cannot_be_shorter_than_read() -> None:
    with pytest.raises(ValidationError, match="NOTIFICATION_UNREAD_RETENTION_DAYS"):
        _settings_with_documented_defaults(
            NOTIFICATION_READ_RETENTION_DAYS=90,
            NOTIFICATION_UNREAD_RETENTION_DAYS=30,
        )
