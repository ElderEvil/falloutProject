"""Convert three achievement rewards to pet carriers.

``sync_achievement_templates`` refreshes track metadata but not rewards, so
existing databases need this explicit update to match ``achievements.json``.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "b6c8d0e2f4a1"
down_revision: str | None = "e5a7c9d1b3f2"
branch_labels = None
depends_on = None

_REWARDS = {
    "achievement:reach 50 dwellers": ("1 pet carrier", "2500 caps"),
    "achievement:complete 5 main quests": ("1 pet carrier", "2500 caps"),
    "achievement:reverse-engineer a legendary": ("1 pet carrier", "1000 caps"),
}
_STATEMENT = sa.text("UPDATE objective SET reward = :reward WHERE template_key = :key")


def _set_rewards(reward_index: int) -> None:
    for key, rewards in _REWARDS.items():
        op.execute(_STATEMENT.bindparams(reward=rewards[reward_index], key=key))


def upgrade() -> None:
    _set_rewards(0)


def downgrade() -> None:
    _set_rewards(1)
