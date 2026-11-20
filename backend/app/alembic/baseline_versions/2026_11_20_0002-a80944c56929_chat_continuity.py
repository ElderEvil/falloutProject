"""Chat continuity: conversation threads, message links, dweller memory.

One permanent thread per (user, dweller) pair; existing messages are backfilled into
threads grouped by pair, never one conversation per stray row.
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID, uuid7

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects.postgresql import JSONB

from app.utils.time import utcnow

revision = "a80944c56929"
down_revision = "9a73f29c2ed1"
branch_labels = None
depends_on = None

#: Lightweight table for the backfill bulk insert (portable across PG and the SQLite fragment tests).
_CONVERSATION_TABLE = sa.table(
    "conversation",
    sa.column("id", sa.UUID),
    sa.column("vault_id", sa.UUID),
    sa.column("user_id", sa.UUID),
    sa.column("dweller_id", sa.UUID),
    sa.column("last_message_at", sa.DateTime(timezone=True)),
    sa.column("message_count", sa.Integer),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

# PostgreSQL has no min(uuid)/max(uuid) aggregate, so the vault is grouped rather than
# aggregated; a pair that somehow spans two vaults is resolved in Python, most active first.
_PAIR_SELECT = sa.text(
    "SELECT user_id, dweller_id, vault_id,"
    " MAX(created_at) AS last_message_at, COUNT(*) AS message_count"
    " FROM ("
    " SELECT vault_id, from_user_id AS user_id, to_dweller_id AS dweller_id, created_at"
    " FROM chatmessage WHERE from_user_id IS NOT NULL AND to_dweller_id IS NOT NULL"
    " UNION ALL"
    " SELECT vault_id, to_user_id AS user_id, from_dweller_id AS dweller_id, created_at"
    " FROM chatmessage WHERE to_user_id IS NOT NULL AND from_dweller_id IS NOT NULL"
    " ) AS pair_messages"
    " GROUP BY user_id, dweller_id, vault_id"
)

_LINK_UPDATE = sa.text(
    "UPDATE chatmessage SET conversation_id = :conversation_id"
    " WHERE (from_user_id = :user_id AND to_dweller_id = :dweller_id)"
    " OR (to_user_id = :user_id AND from_dweller_id = :dweller_id)"
).bindparams(
    sa.bindparam("conversation_id", type_=sa.UUID),
    sa.bindparam("user_id", type_=sa.UUID),
    sa.bindparam("dweller_id", type_=sa.UUID),
)


def upgrade() -> None:
    op.create_table(
        "conversation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("vault_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("dweller_id", sa.UUID(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("summary_through_message_id", sa.UUID(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("context", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["vault_id"], ["vault.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dweller_id"], ["dweller.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["summary_through_message_id"], ["chatmessage.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "dweller_id", name="uq_conversation_user_dweller"),
    )
    op.create_index("ix_conversation_vault_id", "conversation", ["vault_id"])
    op.create_index("ix_conversation_user_id", "conversation", ["user_id"])
    op.create_index("ix_conversation_dweller_id", "conversation", ["dweller_id"])
    op.create_index("ix_conversation_last_message_at", "conversation", ["last_message_at"])

    # Batch mode: direct ALTER on PostgreSQL, copy-and-move on SQLite (no ALTER ADD CONSTRAINT).
    with op.batch_alter_table("chatmessage") as batch_op:
        batch_op.add_column(sa.Column("conversation_id", sa.UUID(), nullable=True))
        batch_op.create_foreign_key("chatmessage_conversation_id_fkey", "conversation", ["conversation_id"], ["id"])
    op.create_index("ix_chatmessage_conversation_id", "chatmessage", ["conversation_id"])

    op.create_table(
        "dweller_memory",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("dweller_id", sa.UUID(), nullable=False),
        sa.Column("fact", sa.Text(), nullable=False),
        sa.Column("fact_hash", sa.String(64), nullable=False),
        sa.Column("source_message_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["dweller_id"], ["dweller.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_message_id"], ["chatmessage.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dweller_id", "fact_hash", name="uq_memory_fact"),
    )
    op.create_index("ix_dweller_memory_id", "dweller_memory", ["id"])
    op.create_index("ix_dweller_memory_dweller_id", "dweller_memory", ["dweller_id"])

    _backfill_conversations()


def _backfill_conversations() -> None:
    """Group legacy messages by (user, dweller) pair: one SELECT, one bulk insert, one batched UPDATE."""
    if context.is_offline_mode():
        return
    bind = op.get_bind()
    grouped = bind.execute(_PAIR_SELECT).mappings().all()
    # A dweller belongs to one vault; if legacy rows disagree, the busiest pair wins.
    pairs: dict[tuple[str, str], Mapping[str, Any]] = {}
    for candidate in grouped:
        key = (str(candidate["user_id"]), str(candidate["dweller_id"]))
        current = pairs.get(key)
        if current is None or candidate["message_count"] > current["message_count"]:
            pairs[key] = candidate
    if not pairs:
        return
    now = utcnow()
    rows = []
    updates = []
    for pair in pairs.values():
        conversation_id = uuid7()
        last_message_at = pair["last_message_at"]
        if isinstance(last_message_at, str):  # SQLite fragment tests read timestamps back as text
            last_message_at = datetime.fromisoformat(last_message_at)
        rows.append(
            {
                "id": conversation_id,
                "vault_id": UUID(str(pair["vault_id"])),
                "user_id": UUID(str(pair["user_id"])),
                "dweller_id": UUID(str(pair["dweller_id"])),
                "last_message_at": last_message_at,
                "message_count": pair["message_count"],
                "created_at": now,
                "updated_at": now,
            }
        )
        updates.append(
            {
                "conversation_id": conversation_id,
                "user_id": UUID(str(pair["user_id"])),
                "dweller_id": UUID(str(pair["dweller_id"])),
            }
        )
    op.bulk_insert(_CONVERSATION_TABLE, rows)
    bind.execute(_LINK_UPDATE, updates)


def downgrade() -> None:
    op.drop_index("ix_dweller_memory_dweller_id", table_name="dweller_memory")
    op.drop_index("ix_dweller_memory_id", table_name="dweller_memory")
    op.drop_table("dweller_memory")
    op.drop_index("ix_chatmessage_conversation_id", table_name="chatmessage")
    with op.batch_alter_table("chatmessage") as batch_op:
        batch_op.drop_column("conversation_id")
    op.drop_index("ix_conversation_last_message_at", table_name="conversation")
    op.drop_index("ix_conversation_dweller_id", table_name="conversation")
    op.drop_index("ix_conversation_user_id", table_name="conversation")
    op.drop_index("ix_conversation_vault_id", table_name="conversation")
    op.drop_table("conversation")
