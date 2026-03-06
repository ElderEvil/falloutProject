import sys
from unittest.mock import MagicMock, patch

import pytest

import app.core.logfire_config as logfire_module
from app.core.config import settings
from app.core.logfire_config import _logfire_state, configure_logfire, is_logfire_enabled


@pytest.fixture(autouse=True)
def _reset_logfire_state():
    _logfire_state.initialized = False


class TestLogfireConfig:
    def test_is_logfire_enabled_returns_false_initially(self):
        assert is_logfire_enabled() is False

    def test_configure_logfire_without_token(self, monkeypatch):
        monkeypatch.setattr(settings, "LOGFIRE_TOKEN", None)
        configure_logfire()

        assert is_logfire_enabled() is False

    def test_configure_logfire_with_token_sets_enabled(self, monkeypatch):
        monkeypatch.setattr(settings, "LOGFIRE_TOKEN", "test_token_for_testing")

        mock_logfire = MagicMock()
        with patch.dict(sys.modules, {"logfire": mock_logfire}):
            configure_logfire()

            mock_logfire.configure.assert_called_once_with(
                token="test_token_for_testing",
                environment=settings.ENVIRONMENT,
                service_name="fallout-shelter-api",
            )
            assert is_logfire_enabled() is True
