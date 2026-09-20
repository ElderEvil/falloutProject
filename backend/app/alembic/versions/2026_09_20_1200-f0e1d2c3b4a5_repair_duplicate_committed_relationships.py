"""repair duplicate committed relationships

A dweller could end up with multiple PARTNER/MARRIED relationship rows:
``make_partners`` and the affinity auto-transition never checked whether either
dweller was already committed to a third dweller, and ``_set_partner_ids`` just
overwrote ``partner_id``, leaving the old committed row intact.

This revision enforces the "one committed relationship per dweller" invariant on
existing data. A deterministic global greedy matching keeps the maximal set of
committed links such that no dweller keeps more than one: links are ranked by
how many of their two dweller sides already point at the other side via
``partner_id`` (then by ``updated_at``), and a link is kept only when neither of
its dwellers was already kept. Every other committed link is demoted to EX
(affinity and updated_at untouched). ``partner_id`` is then synced to the
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

    # Deterministic global greedy matching: keep the maximal set of committed
    # links such that no dweller keeps more than one. A link whose dweller sides
    # already point at each other via partner_id ranks first (then most recently
    # updated), so healthy committed pairs survive and both star and cycle
    # topologies resolve deterministically.
    def _link_key(link: dict) -> tuple[int, datetime]:
        sides_match = int(partner_by_id.get(link["dweller_1_id"]) == link["dweller_2_id"]) + int(
            partner_by_id.get(link["dweller_2_id"]) == link["dweller_1_id"]
        )
        return (sides_match, link["updated_at"] or datetime.min)

    kept_ids: set[str] = set()
    kept_dwellers: set[str] = set()
    for link in sorted(committed_rows, key=_link_key, reverse=True):
        if link["dweller_1_id"] in kept_dwellers or link["dweller_2_id"] in kept_dwellers:
            continue
        kept_ids.add(link["id"])
        kept_dwellers.add(link["dweller_1_id"])
        kept_dwellers.add(link["dweller_2_id"])

    demote_ids = {row["id"] for row in committed_rows} - kept_ids

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

    # Sync partner_id for every dweller that had a committed link: to the kept
    # link's other side, or NULL when none of their links were kept (a demoted
    # dweller must not keep a stale partner_id that would still pair them with
    # the ex-partner in lineage/breeding lookups).
    for dweller_id, links in links_by_dweller.items():
        remaining = [link for link in links if link["id"] in kept_ids]
        conn.execute(
            sa.text("UPDATE dweller SET partner_id = :other_id WHERE id = :dweller_id"),
            {"other_id": remaining[0]["other_id"] if remaining else None, "dweller_id": dweller_id},
        )

    # Clear stale partner_id on dwellers that have no committed link at all.
    # This always runs, even when no committed rows exist: with an empty
    # links_by_dweller every non-null partner_id is stale and must be cleared.
    if links_by_dweller:
        conn.execute(
            sa.text("UPDATE dweller SET partner_id = NULL WHERE partner_id IS NOT NULL AND id NOT IN :ids").bindparams(
                sa.bindparam("ids", expanding=True)
            ),
            {"ids": sorted(links_by_dweller)},
        )
    else:
        conn.execute(sa.text("UPDATE dweller SET partner_id = NULL WHERE partner_id IS NOT NULL"))


def downgrade() -> None:
    """No-op — demoting duplicate committed relationships is an irreversible data repair."""
