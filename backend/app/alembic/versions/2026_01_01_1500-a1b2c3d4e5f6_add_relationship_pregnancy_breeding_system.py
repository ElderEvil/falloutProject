"""add_relationship_pregnancy_breeding_system

Revision ID: a1b2c3d4e5f6
Revises: fa045c06e2ae
Create Date: 2026-01-01 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel  # noqa: F401
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'fa045c06e2ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE: This migration has been squashed to include enum case changes
    # The database now uses uppercase enum values (ADULT, CHILD, TEEN, etc.)

    # Drop existing enum types if they exist (from partial migration) using CASCADE
    op.execute("DROP TYPE IF EXISTS agegroup CASCADE")
    op.execute("DROP TYPE IF EXISTS relationshiptype CASCADE")
    op.execute("DROP TYPE IF EXISTS pregnancystatus CASCADE")

    # Create enum types with uppercase values (matches current DB state)
    op.execute("CREATE TYPE agegroupenum AS ENUM ('CHILD', 'TEEN', 'ADULT')")
    op.execute("CREATE TYPE relationshiptypeenum AS ENUM ('ACQUAINTANCE', 'FRIEND', 'ROMANTIC', 'PARTNER', 'EX')")
    op.execute("CREATE TYPE pregnancystatusenum AS ENUM ('PREGNANT', 'DELIVERED', 'MISCARRIED')")

    # Add new columns to dweller table
    op.add_column('dweller', sa.Column('age_group', postgresql.ENUM('CHILD', 'TEEN', 'ADULT', name='agegroupenum', create_type=False), nullable=False, server_default='ADULT'))
    op.add_column('dweller', sa.Column('birth_date', sa.DateTime(), nullable=True))
    op.add_column('dweller', sa.Column('partner_id', sa.UUID(), nullable=True))
    op.add_column('dweller', sa.Column('parent_1_id', sa.UUID(), nullable=True))
    op.add_column('dweller', sa.Column('parent_2_id', sa.UUID(), nullable=True))

    # Create foreign keys for dweller relationships
    op.create_foreign_key('fk_dweller_partner', 'dweller', 'dweller', ['partner_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_dweller_parent_1', 'dweller', 'dweller', ['parent_1_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_dweller_parent_2', 'dweller', 'dweller', ['parent_2_id'], ['id'], ondelete='SET NULL')

    # Create relationship table
    op.create_table(
        'relationship',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('dweller_1_id', sa.UUID(), nullable=False),
        sa.Column('dweller_2_id', sa.UUID(), nullable=False),
        sa.Column('relationship_type', postgresql.ENUM('ACQUAINTANCE', 'FRIEND', 'ROMANTIC', 'PARTNER', 'EX', name='relationshiptypeenum', create_type=False), nullable=False, server_default='ACQUAINTANCE'),
        sa.Column('affinity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['dweller_1_id'], ['dweller.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dweller_2_id'], ['dweller.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_relationship_id', 'relationship', ['id'])

    # Create pregnancy table
    op.create_table(
        'pregnancy',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('mother_id', sa.UUID(), nullable=False),
        sa.Column('father_id', sa.UUID(), nullable=False),
        sa.Column('conceived_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('due_at', sa.DateTime(), nullable=False),
        sa.Column('status', postgresql.ENUM('PREGNANT', 'DELIVERED', 'MISCARRIED', name='pregnancystatusenum', create_type=False), nullable=False, server_default='PREGNANT'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['mother_id'], ['dweller.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['father_id'], ['dweller.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_pregnancy_id', 'pregnancy', ['id'])


def downgrade() -> None:
    # Drop pregnancy table
    op.drop_index('ix_pregnancy_id', 'pregnancy')
    op.drop_table('pregnancy')

    # Drop relationship table
    op.drop_index('ix_relationship_id', 'relationship')
    op.drop_table('relationship')

    # Drop foreign keys from dweller
    op.drop_constraint('fk_dweller_parent_2', 'dweller', type_='foreignkey')
    op.drop_constraint('fk_dweller_parent_1', 'dweller', type_='foreignkey')
    op.drop_constraint('fk_dweller_partner', 'dweller', type_='foreignkey')

    # Drop columns from dweller
    op.drop_column('dweller', 'parent_2_id')
    op.drop_column('dweller', 'parent_1_id')
    op.drop_column('dweller', 'partner_id')
    op.drop_column('dweller', 'birth_date')
    op.drop_column('dweller', 'age_group')

    # Drop enum types (with IF EXISTS for safety)
    op.execute("DROP TYPE IF EXISTS pregnancystatusenum")
    op.execute("DROP TYPE IF EXISTS relationshiptypeenum")
    op.execute("DROP TYPE IF EXISTS agegroupenum")
