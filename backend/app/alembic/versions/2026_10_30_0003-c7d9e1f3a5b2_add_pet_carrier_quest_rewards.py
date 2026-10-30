"""Add the pet carrier reward to two quest seeds for existing databases.

The seed CLI reconciles quest rewards from JSON, but deploys only run
migrations, so existing rows need this explicit insert. The insert is guarded so
a reseeded database is not given a duplicate carrier.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "c7d9e1f3a5b2"
down_revision: str | None = "b6c8d0e2f4a1"
branch_labels = None
depends_on = None

_QUESTS = {
    "A Poorly Thought-Out Plan": (
        "Lunchbox, Legendary junk, Plasma rifle, Pet Carrier",
        "Lunchbox, Legendary junk, Plasma rifle",
    ),
    "Against the Odds": (
        "Legendary junk, Rare weapon, Pet Carrier, 200 caps",
        "Legendary junk, Rare weapon, 200 caps",
    ),
}
_UPDATE_REWARDS = sa.text("UPDATE quest SET rewards = :rewards WHERE title = :title")
_INSERT = sa.text(
    """
    INSERT INTO questreward (id, quest_id, reward_type, reward_data, reward_chance, item_data)
    SELECT gen_random_uuid(), q.id, 'ITEM',
           '{"item_name": "Pet Carrier", "quantity": 1}'::jsonb,
           1.0,
           '{"name": "Pet Carrier", "item_type": "pet_carrier", "rarity": "common"}'::jsonb
    FROM quest q
    WHERE q.title = :title
      AND NOT EXISTS (
          SELECT 1 FROM questreward r
          WHERE r.quest_id = q.id AND r.reward_data->>'item_name' = 'Pet Carrier'
      )
    """
)
_DELETE = sa.text(
    """
    DELETE FROM questreward r
    USING quest q
    WHERE r.quest_id = q.id
      AND q.title = :title
      AND r.reward_data->>'item_name' = 'Pet Carrier'
    """
)


def _set_rewards(reward_index: int) -> None:
    for title, rewards in _QUESTS.items():
        op.execute(_UPDATE_REWARDS.bindparams(rewards=rewards[reward_index], title=title))


def upgrade() -> None:
    _set_rewards(0)
    for title in _QUESTS:
        op.execute(_INSERT.bindparams(title=title))


def downgrade() -> None:
    for title in _QUESTS:
        op.execute(_DELETE.bindparams(title=title))
    _set_rewards(1)
