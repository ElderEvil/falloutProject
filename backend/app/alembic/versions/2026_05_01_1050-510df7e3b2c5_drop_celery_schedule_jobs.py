"""drop celery_schedule_jobs

Revision ID: 510df7e3b2c5
Revises: de6116eac92a
Create Date: 2026-05-01 10:50:00.717072

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '510df7e3b2c5'
down_revision: Union[str, None] = 'de6116eac92a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('DROP TYPE IF EXISTS "solarevent" CASCADE')
    op.execute('DROP TYPE IF EXISTS "period" CASCADE')
    op.execute('DROP TABLE IF EXISTS "celery_clockedschedule" CASCADE')
    op.execute('DROP TABLE IF EXISTS "celery_periodictaskchanged" CASCADE')
    op.execute('DROP TABLE IF EXISTS "celery_periodictask" CASCADE')
    op.execute('DROP TABLE IF EXISTS "celery_intervalschedule" CASCADE')
    op.execute('DROP TABLE IF EXISTS "celery_crontabschedule" CASCADE')
    op.execute('DROP TABLE IF EXISTS "celery_solarschedule" CASCADE')


def downgrade() -> None:
    op.create_table('celery_solarschedule',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('event', postgresql.ENUM('dawn_astronomical', 'dawn_nautical', 'dawn_civil', 'sunrise', 'solar_noon', 'sunset', 'dusk_civil', 'dusk_nautical', 'dusk_astronomical', name='solarevent'), autoincrement=False, nullable=False),
        sa.Column('latitude', sa.NUMERIC(precision=9, scale=6), autoincrement=False, nullable=False),
        sa.Column('longitude', sa.NUMERIC(precision=9, scale=6), autoincrement=False, nullable=False),
        sa.PrimaryKeyConstraint('id', name='celery_solarschedule_pkey'),
        sa.UniqueConstraint('event', 'latitude', 'longitude', name='celery_solarschedule_event_latitude_longitude_key')
    )
    op.create_table('celery_crontabschedule',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('minute', sa.VARCHAR(length=240), autoincrement=False, nullable=False),
        sa.Column('hour', sa.VARCHAR(length=96), autoincrement=False, nullable=False),
        sa.Column('day_of_week', sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column('day_of_month', sa.VARCHAR(length=124), autoincrement=False, nullable=False),
        sa.Column('month_of_year', sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column('timezone', sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.PrimaryKeyConstraint('id', name='celery_crontabschedule_pkey')
    )
    op.create_table('celery_intervalschedule',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('every', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('period', postgresql.ENUM('days', 'hours', 'minutes', 'seconds', 'microseconds', name='period'), autoincrement=False, nullable=False),
        sa.CheckConstraint('every >= 1', name='celery_intervalschedule_every_check'),
        sa.PrimaryKeyConstraint('id', name='celery_intervalschedule_pkey')
    )
    op.create_table('celery_periodictask',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('name', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
        sa.Column('task', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
        sa.Column('args', sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column('kwargs', sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column('queue', sa.VARCHAR(length=255), autoincrement=True, nullable=True),
        sa.Column('exchange', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
        sa.Column('routing_key', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
        sa.Column('headers', sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column('priority', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('expires', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column('expire_seconds', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('one_off', sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column('start_time', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column('enabled', sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column('last_run_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column('total_run_count', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('date_changed', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column('discriminator', sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column('schedule_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.CheckConstraint('priority >= 0 AND priority <= 255', name='celery_periodictask_priority_check'),
        sa.PrimaryKeyConstraint('id', name='celery_periodictask_pkey'),
        sa.UniqueConstraint('name', name='celery_periodictask_name_key')
    )
    op.create_table('celery_periodictaskchanged',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('last_update', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False),
        sa.PrimaryKeyConstraint('id', name='celery_periodictaskchanged_pkey')
    )
    op.create_table('celery_clockedschedule',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('clocked_time', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.PrimaryKeyConstraint('id', name='celery_clockedschedule_pkey')
    )
