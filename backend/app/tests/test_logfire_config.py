import pytest

from app.core.logfire_config import configure_logfire, is_logfire_enabled


class TestLogfireConfig:
    def test_is_logfire_enabled_returns_false_initially(self):
        assert is_logfire_enabled() is False

    def test_configure_logfire_without_token(self, monkeypatch):
        from app.core import config

        monkeypatch.setattr(config.settings, "LOGFIRE_TOKEN", None)

        configure_logfire()

        assert is_logfire_enabled() is False

    def test_configure_logfire_with_token_sets_enabled(self, monkeypatch):
        from app.core import config

        import importlib
        import app.core.logfire_config as logfire_module

        monkeypatch.setattr(config.settings, "LOGFIRE_TOKEN", "test_token_for_testing")

        logfire_module.configure_logfire()

        assert logfire_module.is_logfire_enabled() is True
