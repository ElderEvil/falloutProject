"""Regression tests for production log-file configuration."""

import logging

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.logging import setup_logging


def test_quest_duration_multiplier_is_local_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("QUEST_DURATION_MULTIPLIER", "0.2")

    with pytest.raises(ValidationError, match="QUEST_DURATION_MULTIPLIER"):
        Settings()


def test_production_uses_persistent_log_file_when_path_is_unset() -> None:
    settings = Settings.model_construct(ENVIRONMENT="production", LOG_FILE_PATH=None)

    assert settings.log_file_path == "/var/log/fallout_shelter/app.log"


def test_explicit_log_file_path_is_preserved() -> None:
    settings = Settings.model_construct(ENVIRONMENT="production", LOG_FILE_PATH="/custom/app.log")

    assert settings.log_file_path == "/custom/app.log"


def test_setup_logging_creates_nested_log_file(tmp_path) -> None:
    root_logger = logging.getLogger()
    previous_handlers = root_logger.handlers[:]
    previous_level = root_logger.level
    log_path = tmp_path / "nested" / "production.log"

    try:
        setup_logging(log_level="INFO", log_file=str(log_path))
        logging.getLogger("test.production").info("production logging check")
        for handler in root_logger.handlers:
            handler.flush()

        assert log_path.is_file()
        assert "production logging check" in log_path.read_text(encoding="utf-8")
    finally:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            handler.close()
        for handler in previous_handlers:
            root_logger.addHandler(handler)
        root_logger.setLevel(previous_level)
