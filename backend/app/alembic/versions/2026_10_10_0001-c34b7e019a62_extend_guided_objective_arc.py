"""Extend the guided arc beyond the Office and link existing tutorial vaults.

Historical paid/completed objectives are untouched. New links start at zero;
state milestones derive existing population/levels at read and claim time.
Downgrade deliberately preserves earned progress and rewards.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "c34b7e019a62"
down_revision = "862c04111ec1"
branch_labels = None
depends_on = None

_STEPS = [
    {
        "challenge": "Train a SPECIAL stat",
        "reward": "200 caps",
        "category": "starter",
        "objective_type": "train",
        "target_entity": {},
        "target_amount": 1,
        "sequence": 9,
        "description": "Build a training room and train one stat. Choose a stat that improves a dweller's next job or quest role.",
    },
    {
        "challenge": "Complete 3 quest missions",
        "reward": "1 lunchbox",
        "category": "starter",
        "objective_type": "expedition",
        "target_entity": {},
        "target_amount": 3,
        "sequence": 10,
        "description": "Use the Overseer's Office to choose missions, prepare a party and claim the rewards after each return.",
    },
    {
        "challenge": "Develop a level 20 dweller",
        "reward": "750 caps",
        "category": "starter",
        "objective_type": "reach",
        "target_entity": {"reach_type": "level"},
        "target_amount": 20,
        "sequence": 11,
        "description": "Develop a veteran through work, quests or exploration. Review newly available missions and their equipment requirements.",
    },
    {
        "challenge": "Grow a 50-dweller vault",
        "reward": "1 lunchbox",
        "category": "starter",
        "objective_type": "reach",
        "target_entity": {"reach_type": "dweller_count"},
        "target_amount": 50,
        "sequence": 12,
        "description": "Expand living space and recruit or raise dwellers. Keep production and medical capacity ahead of population growth.",
    },
]


def upgrade() -> None:
    """Seed name-keyed templates and add only missing tutorial links."""
    connection = op.get_bind()
    objective = sa.table(
        "objective",
        sa.column("id", sa.Uuid()),
        sa.column("challenge", sa.String()),
        sa.column("reward", sa.String()),
        sa.column("category", sa.String()),
        sa.column("objective_type", sa.String()),
        sa.column("target_entity", sa.JSON().with_variant(JSONB(), "postgresql")),
        sa.column("target_amount", sa.Integer()),
        sa.column("sequence", sa.Integer()),
        sa.column("description", sa.String()),
    )
    link = sa.table(
        "vaultobjectiveprogresslink",
        sa.column("vault_id", sa.Uuid()),
        sa.column("objective_id", sa.Uuid()),
        sa.column("progress", sa.Integer()),
        sa.column("total", sa.Integer()),
        sa.column("is_completed", sa.Boolean()),
    )
    from uuid import uuid4

    guided_vaults = list(
        connection.execute(
            sa.select(link.c.vault_id)
            .join(objective, objective.c.id == link.c.objective_id)
            .where(objective.c.category == "starter")
            .distinct()
        ).scalars()
    )
    for step in _STEPS:
        objective_id = connection.execute(
            sa.select(objective.c.id).where(
                sa.func.lower(sa.func.trim(objective.c.challenge)) == step["challenge"].lower()
            )
        ).scalar_one_or_none()
        if objective_id is None:
            objective_id = uuid4()
            connection.execute(objective.insert().values(id=objective_id, **step))
        for vault_id in guided_vaults:
            exists = connection.execute(
                sa.select(link.c.objective_id).where(link.c.vault_id == vault_id, link.c.objective_id == objective_id)
            ).scalar_one_or_none()
            if exists is None:
                connection.execute(
                    link.insert().values(
                        vault_id=vault_id,
                        objective_id=objective_id,
                        progress=0,
                        total=step["target_amount"],
                        is_completed=False,
                    )
                )


def downgrade() -> None:
    """No-op: deleting these links would erase player progress or pending rewards."""
