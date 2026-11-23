import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def test_death_service_log_has_context() -> None:
    source = (BACKEND_ROOT / "app" / "services" / "family" / "death_service.py").read_text()

    # Regression guard: the death log must carry dweller name, cause and vault_id.
    assert '"Dweller %s (%s) died of %s in vault %s"' in source, (
        "logger.info must use a format string with dweller name, cause, and vault_id"
    )
    for fragment in ("dweller.first_name", "dweller.last_name", "cause.value", "dweller.vault_id"):
        assert fragment in source
    assert re.search(r"logger\.info\s*\(\s*cause\.value\s*\)", source) is None, (
        "logger.info must NOT use bare cause.value — it must include dweller/vault context"
    )
