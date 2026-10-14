"""Restore the legacy starter cohort and add versioned revised templates.

The prior revision rewrote shared starter rows in place and retired the withdrawn keys, so
existing vaults silently inherited the revised requirements, sequence and payouts. This
follow-up migration is corrective rather than a rewrite of that applied revision:

* every legacy starter row is restored to its released contract and marked ``assignable =
  False`` so it is no longer handed to new vaults, while its links keep evaluating and
  claiming against the definition they were assigned under;
* the revised definitions are (re)added under their final versioned keys and marked
  ``assignable = True`` so new standard vaults receive the revised track;
* ``vaultobjectiveprogresslink`` is never touched, so link progress, totals, completed
  claims and reward snapshots survive intact;
* the additive ``assignable`` column defaults true for every other category.

``downgrade`` is a no-op: reversing would either erase the revised templates or re-enable
legacy assignment for new vaults.
"""

import json
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "f6a1b2c3d4e5"
down_revision = "e5c2b7f19a04"
branch_labels = None
depends_on = None

_LEGACY = json.loads('''
[{"challenge":"Assign dwellers to Power","reward":"25 caps","category":"starter","objective_type":"assign","target_entity":{"room_type":"power_generator"},"target_amount":3,"sequence":0,"description":"Open the Power Generator and assign dwellers.","template_key":"starter:assign dwellers to power"},{"challenge":"Collect 150 Power","reward":"50 power","category":"starter","objective_type":"collect","target_entity":{"resource_type":"power","production_only":true},"target_amount":150,"sequence":1,"description":"Staff a Power Generator with Strength workers. Gross output counts even when storage is full.","template_key":"starter:collect 150 power"},{"challenge":"Build a Living Quarters","reward":"50 caps","category":"starter","objective_type":"build","target_entity":{"room_type":"living_room"},"target_amount":1,"sequence":2,"description":"More living space lets the vault grow.","template_key":"starter:build a living quarters"},{"challenge":"Assign a dweller correctly","reward":"50 caps","category":"starter","objective_type":"assign_correct","target_entity":{},"target_amount":1,"sequence":3,"description":"Match a dweller's best SPECIAL to the room.","template_key":"starter:assign a dweller correctly"},{"challenge":"Scavenge caps in the wasteland","reward":"100 caps","category":"starter","objective_type":"collect","target_entity":{"resource_type":"caps"},"target_amount":300,"sequence":4,"description":"Send a healthy dweller to explore \u2014 they return with caps and loot.","template_key":"starter:scavenge caps in the wasteland"},{"challenge":"Reach 10 Dwellers","reward":"100 caps","category":"starter","objective_type":"reach","target_entity":{"reach_type":"dweller_count"},"target_amount":10,"sequence":5,"description":"Grow population via the radio or breeding.","template_key":"starter:reach 10 dwellers"},{"challenge":"Reach 18 Dwellers","reward":"150 caps","category":"starter","objective_type":"reach","target_entity":{"reach_type":"dweller_count"},"target_amount":18,"sequence":6,"description":"The Overseer's Office needs 18 dwellers.","template_key":"starter:reach 18 dwellers"},{"challenge":"Build Overseer's Office","reward":"200 caps","category":"starter","objective_type":"build","target_entity":{"room_type":"overseers_office"},"target_amount":1,"sequence":7,"description":"Costs 1000 caps \u2014 keep exploring and selling loot.","template_key":"starter:build overseer's office"},{"challenge":"Reverse-engineer a schematic","reward":"300 caps","category":"starter","objective_type":"scrap","target_entity":{"item_type":"weapon","rarity":"rare"},"target_amount":1,"sequence":8,"description":"Find a rare weapon in the wasteland and scrap it to learn its schematic.","template_key":"starter:reverse-engineer a schematic"},{"challenge":"Train a SPECIAL stat","reward":"200 caps","category":"starter","objective_type":"train","target_entity":{},"target_amount":1,"sequence":9,"description":"Build a training room and train one stat. Choose a stat that improves a dweller's next job or quest role.","template_key":"starter:train a special stat"},{"challenge":"Complete 3 quest missions","reward":"1 lunchbox","category":"starter","objective_type":"expedition","target_entity":{},"target_amount":3,"sequence":10,"description":"Use the Overseer's Office to choose missions, prepare a party and claim the rewards after each return.","template_key":"starter:complete 3 quest missions"},{"challenge":"Develop a level 20 dweller","reward":"750 caps","category":"starter","objective_type":"reach","target_entity":{"reach_type":"level"},"target_amount":20,"sequence":11,"description":"Develop a veteran through work, quests or exploration. Review newly available missions and their equipment requirements.","template_key":"starter:develop a level 20 dweller"},{"challenge":"Grow a 50-dweller vault","reward":"1 lunchbox","category":"starter","objective_type":"reach","target_entity":{"reach_type":"dweller_count"},"target_amount":50,"sequence":12,"description":"Expand living space and recruit or raise dwellers. Keep production and medical capacity ahead of population growth.","template_key":"starter:grow a 50-dweller vault"}]
''')

# The ``#v2`` suffix marks a definition whose requirements, payout or sequence changed from
# the released contract; the new explore step has no legacy counterpart and keeps its key.
_REVISED = json.loads('''
[{"challenge":"Match a dweller to their room","reward":"50 caps","category":"starter","objective_type":"assign_correct","target_entity":{},"target_amount":1,"sequence":0,"description":"Every worker is matched to a room by their best SPECIAL. Open Dwellers to see the match; move someone if you like.","template_key":"starter:assign a dweller correctly#v2"},{"challenge":"Build a Living Quarters","reward":"dweller:Wanderer","category":"starter","objective_type":"build","target_entity":{"room_type":"living_room","additional":true,"baseline_size":3},"target_amount":1,"sequence":1,"description":"More living space raises the population cap. Build another quarter and a new dweller joins the vault.","template_key":"starter:build a living quarters#v2"},{"challenge":"Send a dweller exploring","reward":"50 caps","category":"starter","objective_type":"explore","target_entity":{},"target_amount":1,"sequence":2,"description":"The wasteland returns caps and loot. The run takes hours, so do other things while they are out.","template_key":"starter:send a dweller exploring"},{"challenge":"Reach 10 Dwellers","reward":"100 caps","category":"starter","objective_type":"reach","target_entity":{"reach_type":"dweller_count"},"target_amount":10,"sequence":3,"description":"Grow population via the radio or breeding.","template_key":"starter:reach 10 dwellers#v2"},{"challenge":"Reach 18 Dwellers","reward":"150 caps","category":"starter","objective_type":"reach","target_entity":{"reach_type":"dweller_count"},"target_amount":18,"sequence":4,"description":"The Overseer's Office needs 18 dwellers.","template_key":"starter:reach 18 dwellers#v2"},{"challenge":"Build Overseer's Office","reward":"200 caps","category":"starter","objective_type":"build","target_entity":{"room_type":"overseers_office"},"target_amount":1,"sequence":5,"description":"Costs 1000 caps \u2014 keep exploring and selling loot.","template_key":"starter:build overseer's office#v2"},{"challenge":"Reverse-engineer a schematic","reward":"300 caps","category":"starter","objective_type":"scrap","target_entity":{"item_type":"weapon","rarity":"rare"},"target_amount":1,"sequence":6,"description":"Find a rare weapon in the wasteland and scrap it to learn its schematic.","template_key":"starter:reverse-engineer a schematic#v2"},{"challenge":"Train a SPECIAL stat","reward":"200 caps","category":"starter","objective_type":"train","target_entity":{},"target_amount":1,"sequence":7,"description":"Build a training room and train one stat. Choose a stat that improves a dweller's next job or quest role.","template_key":"starter:train a special stat#v2"},{"challenge":"Complete 3 quest missions","reward":"1 lunchbox","category":"starter","objective_type":"expedition","target_entity":{},"target_amount":3,"sequence":8,"description":"Use the Overseer's Office to choose missions, prepare a party and claim the rewards after each return.","template_key":"starter:complete 3 quest missions#v2"},{"challenge":"Develop a level 20 dweller","reward":"750 caps","category":"starter","objective_type":"reach","target_entity":{"reach_type":"level"},"target_amount":20,"sequence":9,"description":"Develop a veteran through work, quests or exploration. Review newly available missions and their equipment requirements.","template_key":"starter:develop a level 20 dweller#v2"},{"challenge":"Grow a 50-dweller vault","reward":"1 lunchbox","category":"starter","objective_type":"reach","target_entity":{"reach_type":"dweller_count"},"target_amount":50,"sequence":10,"description":"Expand living space and recruit or raise dwellers. Keep production and medical capacity ahead of population growth.","template_key":"starter:grow a 50-dweller vault#v2"}]
''')


def _objective_table():
    return sa.table(
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
        sa.column("template_key", sa.String()),
        sa.column("assignable", sa.Boolean()),
    )


def _existing_id(connection, table, template_key):
    return (
        connection.execute(
            sa.select(table.c.id).where(table.c.template_key == template_key).order_by(table.c.id)
        )
        .scalars()
        .first()
    )


def upgrade() -> None:
    connection = op.get_bind()
    table = _objective_table()

    inspector = sa.inspect(connection)
    if "assignable" not in {column["name"] for column in inspector.get_columns("objective")}:
        op.add_column(
            "objective",
            sa.Column("assignable", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if "ix_objective_assignable" not in {index["name"] for index in inspector.get_indexes("objective")}:
        op.create_index("ix_objective_assignable", "objective", ["assignable"])

    for entry in _LEGACY:
        identifier = _existing_id(connection, table, entry["template_key"])
        if identifier is None:
            continue
        connection.execute(table.update().where(table.c.id == identifier).values(assignable=False, **entry))

    for entry in _REVISED:
        identifier = _existing_id(connection, table, entry["template_key"])
        if identifier is None:
            connection.execute(table.insert().values(id=uuid4(), assignable=True, **entry))
        else:
            connection.execute(table.update().where(table.c.id == identifier).values(assignable=True, **entry))


def downgrade() -> None:
    pass
