"""Test that death_service logging includes full context.

Regression test for A9:
  Before: logger.info(cause.value) — logged bare enum value with no context
  After:  logger.info("Dweller %s (%s) died of %s in vault %s", ...)
"""

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def test_death_service_log_has_context() -> None:
    """death_service must log dweller name, cause, and vault_id — not just cause."""
    svc_path = BACKEND_ROOT / "app" / "services" / "death_service.py"
    source = svc_path.read_text()

    # Must contain context placeholders
    assert (
        '"Dweller %s (%s) died of %s in vault %s"' in source
    ), "logger.info must use a format string with dweller name, cause, and vault_id"
    assert "dweller.first_name" in source
    assert "dweller.last_name" in source
    assert "cause.value" in source
    assert "dweller.vault_id" in source

    # Must NOT use bare cause.value as sole log argument
    import re

    bare_log = re.search(r"logger\.info\s*\(\s*cause\.value\s*\)", source)
    assert bare_log is None, (
        "logger.info must NOT use bare cause.value — it must include dweller/vault context"
    )
