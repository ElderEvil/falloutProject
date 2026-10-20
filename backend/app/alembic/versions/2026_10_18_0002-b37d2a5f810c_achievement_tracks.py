"""Stage achievement families while preserving existing progress and earned rewards."""

import sqlalchemy as sa
from alembic import op

revision = "b37d2a5f810c"
down_revision = "a8c41e06d925"
branch_labels = None
depends_on = None

STAGES = [
    ("achievement:reach 10 dwellers", "reach:dweller_count", 1),
    ("achievement:reach 25 dwellers", "reach:dweller_count", 2),
    ("achievement:reach 50 dwellers", "reach:dweller_count", 3),
    ("achievement:reach 75 dwellers", "reach:dweller_count", 4),
    ("achievement:reach 100 dwellers", "reach:dweller_count", 5),
    ("achievement:build 25 rooms total", "build:*", 1),
    ("achievement:build 50 rooms total", "build:*", 2),
    ("achievement:build a living quarter", "build:living_room", 1),
    ("achievement:collect 10000 caps total", "collect:caps", 1),
    ("achievement:collect 500 power", "collect:power", 2),
    ("achievement:collect 500 food", "collect:food", 2),
    ("achievement:collect 500 water", "collect:water", 2),
    ("achievement:collect 5 stimpaks", "collect:stimpak", 1),
    ("achievement:collect 7 pieces of junk", "collect:junk", 1),
    ("achievement:assign 20 dwellers total", "assign:any", 1),
    ("achievement:assign 50 dwellers total", "assign:any", 2),
    ("achievement:correctly assign 10 total", "assign_correct:any", 1),
    ("achievement:correctly assign 20 total", "assign_correct:any", 2),
    ("achievement:correctly assign 50 total", "assign_correct:any", 3),
    ("achievement:train a dweller", "train:any", 1),
    ("achievement:train dweller to 10 strength", "train:strength", 1),
    ("achievement:train dweller to 10 perception", "train:perception", 1),
    ("achievement:train dweller to 10 endurance", "train:endurance", 1),
    ("achievement:train dweller to 10 charisma", "train:charisma", 1),
    ("achievement:train dweller to 10 intelligence", "train:intelligence", 1),
    ("achievement:train dweller to 10 agility", "train:agility", 1),
    ("achievement:train dweller to 10 luck", "train:luck", 1),
    ("achievement:complete 10 expeditions total", "expedition:any", 1),
    ("achievement:complete 25 expeditions total", "expedition:any", 2),
    ("achievement:complete 50 expeditions total", "expedition:any", 3),
    ("achievement:complete 5 main quests", "expedition:main", 1),
    ("achievement:level up a dweller", "level_up:2", 1),
    ("achievement:reverse-engineer a legendary", "scrap:legendary", 1),
    ("achievement:scrap 10 rare items", "scrap:rare", 1),
    ("achievement:collect 100 power", "collect:power", 1),
    ("achievement:collect 1500 power", "collect:power", 3),
    ("achievement:collect 5000 power", "collect:power", 4),
    ("achievement:collect 100 food", "collect:food", 1),
    ("achievement:collect 1500 food", "collect:food", 3),
    ("achievement:collect 5000 food", "collect:food", 4),
    ("achievement:collect 100 water", "collect:water", 1),
    ("achievement:collect 1500 water", "collect:water", 3),
    ("achievement:collect 5000 water", "collect:water", 4),
]


def upgrade() -> None:
    """Add and backfill achievement family metadata."""
    op.add_column("objective", sa.Column("track_key", sa.String(160), nullable=True))
    op.create_index("ix_objective_track_key", "objective", ["track_key"])
    op.create_index("ix_objective_track_stage", "objective", ["track_key", "sequence"], unique=True)
    op.add_column(
        "vaultobjectiveprogresslink", sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "gamestate",
        sa.Column("achievement_tracks_initialized", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    for key, track, sequence in STAGES:
        op.get_bind().execute(
            sa.text(
                "UPDATE objective SET track_key=:track, sequence=:sequence, template_key=COALESCE(template_key,:key) "
                "WHERE id=(SELECT id FROM objective WHERE category='achievement' AND "
                "(template_key=:key OR (template_key IS NULL AND LOWER(TRIM(challenge))=:name)) "
                "ORDER BY CASE WHEN template_key=:key THEN 0 ELSE 1 END, id LIMIT 1) AND track_key IS NULL"
            ),
            {"key": key, "name": key.removeprefix("achievement:"), "track": track, "sequence": sequence},
        )
    # Preserve every counter and ready reward, but lock later unfinished stages
    # before the first post-deployment production event can credit them.
    op.execute(
        sa.text("""
        UPDATE vaultobjectiveprogresslink AS current_link
        SET is_locked = true
        WHERE current_link.is_completed = false AND current_link.progress < current_link.total
        AND EXISTS (
            SELECT 1 FROM objective current_objective
            JOIN objective previous_objective ON previous_objective.track_key = current_objective.track_key
            JOIN vaultobjectiveprogresslink previous_link ON previous_link.objective_id = previous_objective.id
            WHERE current_objective.id = current_link.objective_id
            AND previous_link.vault_id = current_link.vault_id
            AND previous_objective.sequence < current_objective.sequence
            AND previous_link.is_completed = false AND previous_link.progress < previous_link.total
        )
    """)
    )


def downgrade() -> None:
    """Remove achievement metadata while retaining all objective progress."""
    op.drop_column("gamestate", "achievement_tracks_initialized")
    op.drop_column("vaultobjectiveprogresslink", "is_locked")
    op.drop_index("ix_objective_track_stage", table_name="objective")
    op.drop_index("ix_objective_track_key", table_name="objective")
    op.drop_column("objective", "track_key")
