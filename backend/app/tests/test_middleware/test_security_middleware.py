import pytest

from app.core.config import settings
from app.middleware.security import create_security_config


def test_create_security_config_without_ipinfo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "IPINFO_TOKEN", None, raising=False)

    config = create_security_config()

    assert config.geo_ip_handler is None
