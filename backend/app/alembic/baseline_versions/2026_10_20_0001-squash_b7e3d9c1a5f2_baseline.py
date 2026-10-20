"""Experimental PostgreSQL baseline through b7e3d9c1a5f2.

Opt in with alembic-squash.ini. Existing databases must finish the legacy
history before an explicitly verified stamp; this is not an upgrade from an
arbitrary historical revision. The SQL snapshot contains no local player data.
"""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

from app.core.config import settings
from app.core.security import get_password_hash

revision = "squash_b7e3d9c1a5f2"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the frozen schema and seeds for a new PostgreSQL database."""
    # One PostgreSQL statement works with asyncpg and Alembic's offline output.
    # DDL avoids interpreting colons in frozen prompt/catalog prose as binds.
    snapshot = Path(__file__).with_name("baseline_b7e3d9c1a5f2.sql").read_text()
    op.execute(sa.DDL("DO $fallout_baseline$ BEGIN\n" + snapshot + "\nEND $fallout_baseline$;"))
    _seed_bootstrap_accounts()


def _seed_bootstrap_accounts() -> None:
    """Preserve the initial migration's environment-based admin and demo vault.

    Passwords are hashed at execution time, never frozen in the SQL snapshot.
    Player backfills need no replay on an empty database; already-upgraded
    databases adopt the baseline with stamp, so their rows remain untouched.
    """
    for username, email, password, is_superuser in (
        (
            settings.FIRST_SUPERUSER_USERNAME,
            settings.FIRST_SUPERUSER_EMAIL,
            settings.FIRST_SUPERUSER_PASSWORD,
            True,
        ),
        ("TestUser", settings.EMAIL_TEST_USER, "testpassword", False),
    ):
        op.execute(
            sa.text(
                'INSERT INTO public."user" '
                "(id, username, email, hashed_password, is_superuser, is_active, email_verified, created_at, updated_at) "
                "VALUES (gen_random_uuid(), :username, :email, :password, :is_superuser, true, true, now(), now()) "
                "ON CONFLICT (email) DO NOTHING"
            ).bindparams(
                username=username,
                email=email,
                password=get_password_hash(password),
                is_superuser=is_superuser,
            ),
        )
    op.execute(
        sa.text(
            "INSERT INTO public.vault "
            "(id, number, bottle_caps, happiness, power, power_max, food, food_max, water, water_max, "
            "population_max, radio_mode, user_id, created_at, updated_at) "
            "SELECT gen_random_uuid(), 101, 1000, 50, 50, 100, 100, 200, 100, 200, 200, 'recruitment', "
            'id, now(), now() FROM public."user" WHERE email = :email'
        ).bindparams(email=settings.EMAIL_TEST_USER),
    )
    op.execute(
        sa.text(
            "INSERT INTO public.vaultslot (id, slot_index, vault_id, created_at, updated_at) "
            "SELECT gen_random_uuid(), 0, id, now(), now() FROM public.vault WHERE number = 101"
        )
    )


def downgrade() -> None:
    """Reject attempts to erase the baseline's schema and player data."""
    raise RuntimeError("The experimental baseline cannot be downgraded; restore a backup or use the legacy history.")
