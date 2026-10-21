"""Merge radio retirement and training/quest migrations.

Revision ID: f7a1c3e5b902
Revises: d9e2f4a6b801, e4b8d2a6c1f9
"""

revision = "f7a1c3e5b902"
down_revision = ("d9e2f4a6b801", "e4b8d2a6c1f9")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Preserve both published revision identities and run each parent's missing branch.
    pass


def downgrade() -> None:
    pass
