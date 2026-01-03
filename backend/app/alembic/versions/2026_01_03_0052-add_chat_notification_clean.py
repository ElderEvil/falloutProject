"""Add ChatMessage and Notification models (clean)

Revision ID: add_chat_notif_clean
Revises: 51ec51a1cb9c
Create Date: 2026-01-03 00:52:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_chat_notif_clean'
down_revision: Union[str, None] = '51ec51a1cb9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ChatMessage table
    op.create_table('chatmessage',
    sa.Column('vault_id', sa.Uuid(), nullable=False),
    sa.Column('from_user_id', sa.Uuid(), nullable=True),
    sa.Column('from_dweller_id', sa.Uuid(), nullable=True),
    sa.Column('to_user_id', sa.Uuid(), nullable=True),
    sa.Column('to_dweller_id', sa.Uuid(), nullable=True),
    sa.Column('message_text', sqlmodel.sql.sqltypes.AutoString(length=2000), nullable=False),
    sa.Column('llm_interaction_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['from_dweller_id'], ['dweller.id'], ),
    sa.ForeignKeyConstraint(['from_user_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['llm_interaction_id'], ['llminteraction.id'], ),
    sa.ForeignKeyConstraint(['to_dweller_id'], ['dweller.id'], ),
    sa.ForeignKeyConstraint(['to_user_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['vault_id'], ['vault.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chatmessage_created_at'), 'chatmessage', ['created_at'], unique=False)
    op.create_index(op.f('ix_chatmessage_from_dweller_id'), 'chatmessage', ['from_dweller_id'], unique=False)
    op.create_index(op.f('ix_chatmessage_from_user_id'), 'chatmessage', ['from_user_id'], unique=False)
    op.create_index(op.f('ix_chatmessage_id'), 'chatmessage', ['id'], unique=False)
    op.create_index(op.f('ix_chatmessage_to_dweller_id'), 'chatmessage', ['to_dweller_id'], unique=False)
    op.create_index(op.f('ix_chatmessage_to_user_id'), 'chatmessage', ['to_user_id'], unique=False)
    op.create_index(op.f('ix_chatmessage_vault_id'), 'chatmessage', ['vault_id'], unique=False)

    # Create Notification enum types if they don't exist
    notification_type_enum = postgresql.ENUM(
        'EXPLORATION_UPDATE', 'EXPLORATION_COMPLETE', 'LEVEL_UP', 'TRAINING_COMPLETE',
        'TRAINING_STARTED', 'RELATIONSHIP_FORMED', 'PREGNANCY_DETECTED', 'BABY_BORN',
        'COMBAT_STARTED', 'COMBAT_VICTORY', 'COMBAT_DEFEAT', 'DWELLER_INJURED',
        'RESOURCE_LOW', 'RESOURCE_CRITICAL', 'POWER_OUTAGE', 'QUEST_COMPLETE',
        'ACHIEVEMENT_UNLOCKED', 'RADIO_NEW_DWELLER',
        name='notificationtype',
        create_type=False  # Type might already exist
    )

    notification_priority_enum = postgresql.ENUM(
        'INFO', 'NORMAL', 'HIGH', 'URGENT',
        name='notificationpriority',
        create_type=False  # Type might already exist
    )

    # Create the enum types explicitly (will skip if they exist)
    try:
        notification_type_enum.create(op.get_bind(), checkfirst=True)
    except:
        pass

    try:
        notification_priority_enum.create(op.get_bind(), checkfirst=True)
    except:
        pass

    # Create Notification table
    op.create_table('notification',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('vault_id', sa.Uuid(), nullable=True),
    sa.Column('from_dweller_id', sa.Uuid(), nullable=True),
    sa.Column('notification_type', notification_type_enum, nullable=False),
    sa.Column('priority', notification_priority_enum, nullable=False),
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
    sa.Column('message', sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=False),
    sa.Column('is_read', sa.Boolean(), nullable=False),
    sa.Column('is_dismissed', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('meta_data', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('read_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['from_dweller_id'], ['dweller.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['vault_id'], ['vault.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notification_created_at'), 'notification', ['created_at'], unique=False)
    op.create_index(op.f('ix_notification_from_dweller_id'), 'notification', ['from_dweller_id'], unique=False)
    op.create_index(op.f('ix_notification_id'), 'notification', ['id'], unique=False)
    op.create_index(op.f('ix_notification_is_dismissed'), 'notification', ['is_dismissed'], unique=False)
    op.create_index(op.f('ix_notification_is_read'), 'notification', ['is_read'], unique=False)
    op.create_index(op.f('ix_notification_notification_type'), 'notification', ['notification_type'], unique=False)
    op.create_index(op.f('ix_notification_priority'), 'notification', ['priority'], unique=False)
    op.create_index(op.f('ix_notification_user_id'), 'notification', ['user_id'], unique=False)
    op.create_index(op.f('ix_notification_vault_id'), 'notification', ['vault_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_notification_vault_id'), table_name='notification')
    op.drop_index(op.f('ix_notification_user_id'), table_name='notification')
    op.drop_index(op.f('ix_notification_priority'), table_name='notification')
    op.drop_index(op.f('ix_notification_notification_type'), table_name='notification')
    op.drop_index(op.f('ix_notification_is_read'), table_name='notification')
    op.drop_index(op.f('ix_notification_is_dismissed'), table_name='notification')
    op.drop_index(op.f('ix_notification_id'), table_name='notification')
    op.drop_index(op.f('ix_notification_from_dweller_id'), table_name='notification')
    op.drop_index(op.f('ix_notification_created_at'), table_name='notification')
    op.drop_table('notification')
    op.drop_index(op.f('ix_chatmessage_vault_id'), table_name='chatmessage')
    op.drop_index(op.f('ix_chatmessage_to_user_id'), table_name='chatmessage')
    op.drop_index(op.f('ix_chatmessage_to_dweller_id'), table_name='chatmessage')
    op.drop_index(op.f('ix_chatmessage_id'), table_name='chatmessage')
    op.drop_index(op.f('ix_chatmessage_from_user_id'), table_name='chatmessage')
    op.drop_index(op.f('ix_chatmessage_from_dweller_id'), table_name='chatmessage')
    op.drop_index(op.f('ix_chatmessage_created_at'), table_name='chatmessage')
    op.drop_table('chatmessage')
