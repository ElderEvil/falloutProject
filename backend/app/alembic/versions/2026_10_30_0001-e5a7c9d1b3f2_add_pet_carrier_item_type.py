"""Allow the generic ``pet_carrier`` item category.

Downgrade restores the previous CHECK constraint and therefore fails while any
``pet_carrier`` row still exists; delete or convert those rows first.
"""

from alembic import op

revision: str = "e5a7c9d1b3f2"
down_revision: str | None = "c4f8a2d6e1b9"
branch_labels = None
depends_on = None

_OLD_TYPES = "'misc', 'weapon', 'outfit', 'junk', 'consumable', 'lunchbox', 'pet', 'dweller'"
_NEW_TYPES = "'misc', 'weapon', 'outfit', 'junk', 'consumable', 'lunchbox', 'pet_carrier', 'pet', 'dweller'"


def upgrade() -> None:
    op.drop_constraint("ck_item_item_type", "item", type_="check")
    op.create_check_constraint(
        "ck_item_item_type", "item", f"item_type IN ({_NEW_TYPES})", postgresql_not_valid=True
    )
    with op.get_context().autocommit_block():
        op.execute("ALTER TABLE item VALIDATE CONSTRAINT ck_item_item_type")


def downgrade() -> None:
    op.drop_constraint("ck_item_item_type", "item", type_="check")
    op.create_check_constraint(
        "ck_item_item_type", "item", f"item_type IN ({_OLD_TYPES})", postgresql_not_valid=True
    )
    with op.get_context().autocommit_block():
        op.execute("ALTER TABLE item VALIDATE CONSTRAINT ck_item_item_type")
