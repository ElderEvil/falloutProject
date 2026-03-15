"""add_token_fields_to_llm_interaction

Revision ID: b19deb098d13
Revises: ca055b638262
Create Date: 2026-02-19 18:18:05.257131

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "b19deb098d13"
down_revision: Union[str, None] = "ca055b638262"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("llminteraction", sa.Column("prompt_tokens", sa.Integer(), nullable=True))
    op.add_column("llminteraction", sa.Column("completion_tokens", sa.Integer(), nullable=True))
    op.add_column("llminteraction", sa.Column("total_tokens", sa.Integer(), nullable=True))

    op.create_index(op.f("ix_llminteraction_user_id"), "llminteraction", ["user_id"], unique=False)
    op.create_index(op.f("ix_llminteraction_created_at"), "llminteraction", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_llminteraction_created_at"), table_name="llminteraction")
    op.drop_index(op.f("ix_llminteraction_user_id"), table_name="llminteraction")

    op.drop_column("llminteraction", "total_tokens")
    op.drop_column("llminteraction", "completion_tokens")
    op.drop_column("llminteraction", "prompt_tokens")
