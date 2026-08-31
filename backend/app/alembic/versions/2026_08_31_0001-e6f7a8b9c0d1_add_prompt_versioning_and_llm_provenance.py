"""Add prompt versioning and LLM interaction provenance.

Revision ID: e6f7a8b9c0d1
Revises: b4c5d6e7f8a9
Create Date: 2026-08-31 00:00:00.000000

"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "b4c5d6e7f8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PROMPT_SEEDS = {
    "backstory": (
        "Backstory generation for new dwellers (backstory_agent v1).",
        "You are a creative writer specialized in creating Fallout game series style character biographies. "
        "Generate immersive, lore-accurate backstories for vault dwellers in the post-apocalyptic world. "
        "Use the dweller's SPECIAL attributes to inform their skills and personality traits. "
        "IMPORTANT: Keep biographies between 600-900 characters (not words). Be concise and focused. "
        "Focus on their background, survival skills, and how they relate to their environment. "
        "You MUST also specify origin_place: a specific settlement/place the dweller comes from. "
        "Invent a proper-noun Fallout-style name (e.g. 'Megaton', 'Shady Sands', 'Goodneighbor'). "
        "NEVER use generic names like 'Wasteland', 'the wastes', 'Unknown', or 'Vault'. "
        "Also list 0-5 visited_places: other notable named places the dweller has travelled to, "
        "each a proper-noun Fallout-style location name (max 64 chars each).",
    ),
    "extend_bio": (
        "Bio extension for existing dweller biographies (bio_extension_agent v1).",
        "You are a creative writer helping to extend character biographies in the Fallout universe. "
        "Given an existing bio, add meaningful details that expand on the character's backstory, "
        "experiences, relationships, or personality. Maintain consistency with the original bio "
        "and keep the tone consistent with the Fallout game series. "
        "While extending, if you mention any NEW named Fallout-style locations "
        "(settlements, outposts, vaults, landmarks), list them in visited_places "
        "(0-3 proper-noun names, max 64 chars each). "
        "Only include places you introduce in the extension — do NOT repeat places from the original bio.",
    ),
    "visual_attributes": (
        "Visual attributes generation from dweller bios (visual_attributes_agent v1).",
        "You are a character design specialist for the Fallout universe. "
        "Generate visual attributes for vault dwellers based on their biography and characteristics. "
        "Create realistic, lore-appropriate visual descriptions that match the post-apocalyptic setting.",
    ),
    "chat": (
        "In-character dweller chat with sentiment and action suggestions (dweller_chat_agent v1).",
        "You are a Vault-Tec Dweller in a post-apocalyptic world. "
        "Respond in character, staying true to the Fallout universe. "
        "Analyze the conversation sentiment and suggest helpful actions when appropriate. "
        "Actions include: assigning to any room type in the vault "
        "(production, training, crafting, capacity, misc, quests, or theme rooms), "
        "sending dweller on wasteland exploration, or recalling dweller from exploration. "
        "Only suggest actions when the conversation naturally leads to them (e.g., dweller mentions being bored, "
        "wanting to work, wanting adventure, or wanting to come home). "
        "When the user requests assignment to a specific room, follow their order strictly.",
    ),
}


def _column_names(inspector: sa.Inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def _seed_prompts() -> None:
    """Insert immutable v1 prompts, without replacing legacy or administrator-managed rows."""
    statement = sa.text(
        "INSERT INTO prompt (id, prompt_name, description, prompt_template, version, is_active) "
        "SELECT :id, :prompt_name, :description, :prompt_template, 1, true "
        "WHERE NOT EXISTS (SELECT 1 FROM prompt WHERE prompt_name = :prompt_name)"
    )
    for prompt_name, (description, prompt_template) in PROMPT_SEEDS.items():
        op.get_bind().execute(
            statement,
            {
                "id": str(uuid5(NAMESPACE_URL, f"falloutProject:prompt:{prompt_name}:v1")),
                "prompt_name": prompt_name,
                "description": description,
                "prompt_template": prompt_template,
            },
        )


def upgrade() -> None:
    """Version the prompt registry and snapshot LLM call provenance.

    server_default backfills existing rows (version=1, is_active=true) and is
    dropped afterwards so the schema matches the model metadata. Guards keep
    the migration safe to re-run after a partially applied attempt.
    """
    inspector = sa.inspect(op.get_bind())

    prompt_cols = _column_names(inspector, "prompt")
    needs_normalization = "version" not in prompt_cols or "is_active" not in prompt_cols
    prompt_indexes = {i["name"] for i in inspector.get_indexes("prompt")}
    prompt_constraints = {c["name"] for c in inspector.get_unique_constraints("prompt")}
    with op.batch_alter_table("prompt") as batch_op:
        if "version" not in prompt_cols:
            batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        if "is_active" not in prompt_cols:
            batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

    if needs_normalization:
        rows = op.get_bind().execute(sa.text("SELECT id, prompt_name FROM prompt ORDER BY prompt_name, id")).mappings()
        versions: dict[str, int] = {}
        normalized = []
        for row in rows:
            version = versions.get(row["prompt_name"], 0) + 1
            versions[row["prompt_name"]] = version
            normalized.append({"id": row["id"], "version": version, "is_active": version == 1})
        if normalized:
            op.get_bind().execute(
                sa.text("UPDATE prompt SET version = :version, is_active = :is_active WHERE id = :id"), normalized
            )

    with op.batch_alter_table("prompt") as batch_op:
        if "version" not in prompt_cols:
            batch_op.alter_column("version", server_default=None)
        if "is_active" not in prompt_cols:
            batch_op.alter_column("is_active", server_default=None)
        # Pre-existing field indexes were silently skipped (pydantic Field import); backfill metadata parity.
        for name, column in (
            ("ix_prompt_prompt_name", "prompt_name"),
            ("ix_prompt_entity_id", "entity_id"),
            ("ix_prompt_is_active", "is_active"),
        ):
            if name not in prompt_indexes:
                batch_op.create_index(name, [column], unique=False)
        if "uq_prompt_name_version" not in prompt_constraints:
            batch_op.create_unique_constraint("uq_prompt_name_version", ["prompt_name", "version"])
        if "ix_prompt_active_name" not in prompt_indexes:
            batch_op.create_index(
                "ix_prompt_active_name",
                ["prompt_name"],
                unique=True,
                postgresql_where=sa.text("is_active = true"),
                sqlite_where=sa.text("is_active = true"),
            )

    _seed_prompts()

    interaction_cols = _column_names(inspector, "llminteraction")
    provenance_columns = {
        "provider": sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
        "model": sa.Column("model", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=True),
        "instructions_hash": sa.Column("instructions_hash", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        "instructions_snapshot": sa.Column("instructions_snapshot", sa.Text(), nullable=True),
    }
    for name, column in provenance_columns.items():
        if name not in interaction_cols:
            op.add_column("llminteraction", column)


def downgrade() -> None:
    """Remove prompt versioning and LLM provenance columns."""
    op.drop_column("llminteraction", "instructions_snapshot")
    op.drop_column("llminteraction", "instructions_hash")
    op.drop_column("llminteraction", "model")
    op.drop_column("llminteraction", "provider")
    with op.batch_alter_table("prompt") as batch_op:
        batch_op.drop_index("ix_prompt_active_name")
        batch_op.drop_index("ix_prompt_is_active")
        batch_op.drop_constraint("uq_prompt_name_version", type_="unique")
        batch_op.drop_column("is_active")
        batch_op.drop_column("version")
