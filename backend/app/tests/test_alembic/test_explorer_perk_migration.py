"""Existing residents receive an empty choice, never a randomly assigned perk."""

import pytest

from app.tests.test_alembic import test_data_migrations as legacy

harness = legacy.harness


@pytest.mark.integration
def test_adds_nullable_perk_without_changing_existing_residents(harness):
    harness.upgrade("d1f3a5c7e9b2")
    vault_id = legacy._seed_vault(harness, number=931)
    dweller_id = legacy._seed_lifecycle_dweller(
        harness, vault_id=vault_id, first_name="Legacy", is_dead=False, is_permanently_dead=False
    )
    harness.upgrade("e7a1b3c5d9f2")
    assert harness.fetch("SELECT selected_perk, first_name FROM dweller WHERE id = :id", id=dweller_id) == [
        (None, "Legacy")
    ]
    assert (
        harness.scalar(
            "SELECT count(*) FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid "
            "WHERE t.typname = 'notificationtype' AND e.enumlabel = 'PERK_UNLOCKED'"
        )
        == 1
    )
