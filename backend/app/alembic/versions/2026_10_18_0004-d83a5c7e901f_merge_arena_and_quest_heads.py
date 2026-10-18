"""Join Arena combat and quest text migrations into one upgrade head.

Both branches start at b37d2a5f810c and change independent tables. A merge
revision preserves deployments that already applied either branch.
"""

revision = "d83a5c7e901f"
down_revision = ("c72b4e6f109a", "c7f9a1b3d5e7")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
