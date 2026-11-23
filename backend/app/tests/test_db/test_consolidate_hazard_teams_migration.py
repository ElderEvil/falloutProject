from app.tests.test_alembic._support import load_migration

MIGRATION = load_migration(
    "2026_09_19_0003-c9d8e7f6a5b4_consolidate_hazard_teams_onto_team_roster.py", "consolidate_hazard_teams"
)


def test_revision_chain() -> None:
    assert MIGRATION.down_revision == "b7c8d9e0f1a2"


def test_three_way_purpose_check_covers_all_purposes() -> None:
    sql = MIGRATION.THREE_WAY_PURPOSE_CHECK
    assert "quest_id IS NOT NULL" in sql
    assert "incident_id IS NOT NULL" in sql
    assert "hazard_team IS NOT NULL" in sql


def test_downgrade_restores_two_way_purpose_check() -> None:
    sql = MIGRATION.TWO_WAY_PURPOSE_CHECK
    assert "quest_id IS NOT NULL" in sql
    assert "incident_id IS NOT NULL" in sql
    assert "hazard_team IS NOT NULL" not in sql


def test_member_backfill_assigns_slots_to_living_active_only() -> None:
    sql = str(MIGRATION.MEMBER_BACKFILL_SQL)
    assert "ROW_NUMBER() OVER" in sql
    assert "status = 'active'" in sql
    assert "is_dead = FALSE" in sql
    assert "is_deleted = FALSE" in sql
    assert "slot_number" in sql


def test_member_backfill_caps_active_slots_at_the_roster_size() -> None:
    sql = str(MIGRATION.MEMBER_BACKFILL_SQL)
    limit = MIGRATION.ACTIVE_SLOT_LIMIT
    assert limit == 3
    assert f"ranked.slot_rank <= {limit} THEN ranked.slot_rank" in sql
    assert f"ranked.slot_rank <= {limit} THEN 'active' ELSE 'reserve'" in sql


def test_member_backfill_derives_status_from_slot_occupancy() -> None:
    # Status is never copied: a slot-less row that stayed active would count as a responder.
    assert "ELSE htm.status" not in str(MIGRATION.MEMBER_BACKFILL_SQL)


def test_member_backfill_copies_timestamps() -> None:
    sql = str(MIGRATION.MEMBER_BACKFILL_SQL)
    assert "htm.created_at" in sql
    assert "htm.updated_at" in sql


def test_team_backfill_groups_by_vault_and_hazard() -> None:
    sql = str(MIGRATION.TEAM_BACKFILL_SQL)
    assert "GROUP BY vault_id, team" in sql
    assert "hazard_team" in sql


def test_downgrade_restores_members_from_hazard_teams() -> None:
    sql = str(MIGRATION.MEMBER_RESTORE_SQL)
    assert "hazard_team IS NOT NULL" in sql
    assert "tm.created_at" in sql
    assert "tm.updated_at" in sql
