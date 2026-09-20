"""repair duplicate committed relationships

A dweller could end up with multiple PARTNER/MARRIED relationship rows:
``make_partners`` and the affinity auto-transition never checked whether either
dweller was already committed to a third dweller, and ``_set_partner_ids`` just
overwrote ``partner_id``, leaving the old committed row intact.

This revision enforces the "one committed relationship per dweller" invariant on
existing data. For every dweller with more than one committed link the canonical
link is the one whose other side matches the dweller's current ``partner_id``
(falling back to the most recently updated link); every other link is demoted to
EX (affinity and updated_at untouched). ``partner_id`` is then synced to the
surviving committed link for every committed dweller, and cleared for dwellers
that have no committed link but a stale non-null ``partner_id``.

The repair is idempotent: demoted rows are no longer PARTNER/MARRIED on a re-run,
and the partner_id syncs are plain assignments of the same value.

Revision ID: f0e1d2c3b4a5
Revises: 32bf7f844093
Create Date: 2026-09-20 12:00:00.000000

"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f0e1d2c3b4a5"
down_revision: str | None = "32bf7f844093"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COMMITTED_TYPES = ("PARTNER", "MARRIED")


def upgrade() -> None:
    """Demote duplicate committed relationships and sync partner_id columns."""
    conn = op.get_bind()

    committed_rows = conn.execute(
        sa.text(
            "SELECT id, dweller_1_id, dweller_2_id, updated_at FROM relationship "
            "WHERE relationship_type IN :types AND dweller_1_id IS NOT NULL AND dweller_2_id IS NOT NULL"
        ).bindparams(sa.bindparam("types", expanding=True)),
        {"types": COMMITTED_TYPES},
    ).mappings().all()

    if not committed_rows:
        return

    # Per-dweller committed links: dweller_id -> list of (rel_id, other_id, updated_at).
    links_by_dweller: dict[str, list[dict]] = {}
    for row in committed_rows:
        for dweller_id, other_id in (
            (row["dweller_1_id"], row["dweller_2_id"]),
            (row["dweller_2_id"], row["dweller_1_id"]),
        ):
            links_by_dweller.setdefault(dweller_id, []).append(
                {"id": row["id"], "other_id": other_id, "updated_at": row["updated_at"]}
            )

    partner_rows = conn.execute(sa.text("SELECT id, partner_id FROM dweller")).mappings().all()
    partner_by_id = {row["id"]: row["partner_id"] for row in partner_rows}

    # Demote every non-canonical committed link to EX.
    demote_ids: set[str] = set()
    for dweller_id, links in links_by_dweller.items():
        if len(links) <= 1:
            continue
        canonical = next(
            (link for link in links if link["other_id"] == partner_by_id.get(dweller_id)),
            max(links, key=lambda link: link["updated_at"] or datetime.min),
        )
        demote_ids.update(link["id"] for link in links if link["id"] != canonical["id"])

    if demote_ids:
        conn.execute(
            sa.text(
                "UPDATE relationship SET relationship_type = 'EX' "
                "WHERE id IN :ids AND relationship_type IN :types"
            ).bindparams(
                sa.bindparam("ids", expanding=True),
                sa.bindparam("types", expanding=True),
            ),
            {"ids": sorted(demote_ids), "types": COMMITTED_TYPES},
        )

    # Sync partner_id for every dweller that had a committed link: to the
    # surviving committed link's other side, or NULL when every link they had was
    # demoted (a demoted dweller must not keep a stale partner_id that would
    # still pair them with the ex-partner in lineage/breeding lookups).
    for dweller_id, links in links_by_dweller.items():
        remaining = [link for link in links if link["id"] not in demote_ids]
        conn.execute(
            sa.text("UPDATE dweller SET partner_id = :other_id WHERE id = :dweller_id"),
            {"other_id": remaining[0]["other_id"] if remaining else None, "dweller_id": dweller_id},
        )

    # Clear stale partner_id on dwellers that have no committed link at all.
    conn.execute(
        sa.text("UPDATE dweller SET partner_id = NULL WHERE partner_id IS NOT NULL AND id NOT IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"ids": sorted(links_by_dweller)},
    )


def downgrade() -> None:
    """No-op — demoting duplicate committed relationships is an irreversible data repair."""
