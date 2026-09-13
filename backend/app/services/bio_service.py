"""Living biographies — structured entries compiled into Dweller.bio.

``bio_entries`` is the structured narrative the dossier renders; ``Dweller.bio``
is the plain-text cache read by prompts, chat context, and older surfaces.
Template entries render first, later life events follow chronologically.
"""

import logging
from datetime import datetime
from typing import Any, Protocol

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import BIO_MAX_CHARS, Dweller
from app.schemas.dweller import DwellerUpdate

logger = logging.getLogger(__name__)


class BioEntryOwner(Protocol):
    """Shape carrying a plain-text bio and its structured entries."""

    bio: str | None
    bio_entries: list[dict[str, Any]]


BIO_ENTRY_CAP = 12

# Single authority for how entry sources group into dossier sections; the
# frontend mirrors these keys for labels and falls back for anything unknown.
BIO_SECTIONS: dict[str, tuple[str, ...]] = {
    "origin": ("template", "legacy", "reflection"),
    "exploration": ("exploration",),
    "family": ("family",),
    "dialogue": ("dialogue",),
}
BIO_ENTRY_SOURCES = tuple(source for sources in BIO_SECTIONS.values() for source in sources)
BIO_ORIGIN_SOURCES = BIO_SECTIONS["origin"]


def make_entry(source: str, text: str, ref: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build one timestamped bio entry; raises on unknown sources."""
    if source not in BIO_ENTRY_SOURCES:
        msg = f"Unknown bio entry source: {source}"
        raise ValueError(msg)
    return {
        "source": source,
        "text": text,
        "ref": ref or {},
        "created_at": datetime.utcnow().isoformat(),
    }


def truncate_bio(text: str, limit: int = BIO_MAX_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def cap_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the newest entries, never dropping the origin story."""
    if len(entries) <= BIO_ENTRY_CAP:
        return list(entries)
    protected = [entry for entry in entries if entry.get("source") in BIO_ORIGIN_SOURCES]
    rest = [entry for entry in entries if entry.get("source") not in BIO_ORIGIN_SOURCES]
    keep = BIO_ENTRY_CAP - len(protected)
    return protected + rest[-keep:] if keep > 0 else protected[:BIO_ENTRY_CAP]


def compile_bio(entries: list[dict[str, Any]]) -> str:
    """Render entries to bio text: origin first, then life events in order."""
    remaining = cap_entries(entries)
    while True:
        ordered = [entry for entry in remaining if entry.get("source") in BIO_ORIGIN_SOURCES]
        ordered += [entry for entry in remaining if entry.get("source") not in BIO_ORIGIN_SOURCES]
        text = " ".join(entry.get("text", "") for entry in ordered if entry.get("text"))
        if len(text) <= BIO_MAX_CHARS:
            return text
        victim = next(
            (entry for entry in remaining if entry.get("source") not in BIO_ORIGIN_SOURCES),
            None,
        )
        if victim is None:
            return truncate_bio(text)
        remaining = [entry for entry in remaining if entry is not victim]


class BioService:
    """Append-only bio entries with the rendered bio recompiled on every write."""

    @staticmethod
    def with_entry(
        dweller: BioEntryOwner,
        source: str,
        text: str,
        ref: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return the entry list with one appended, wrapping pre-entries bio text once."""
        entries = list(dweller.bio_entries or [])
        if not entries and dweller.bio:
            entries.append(make_entry("legacy", dweller.bio))
        entries.append(make_entry(source, text, ref))
        return cap_entries(entries)

    @staticmethod
    def replace_origin(text: str) -> list[dict[str, Any]]:
        """Return a fresh entry list carrying only a new origin story."""
        return [make_entry("template", text)]

    @staticmethod
    async def _persist(db_session: AsyncSession, dweller_id: UUID4, entries: list[dict[str, Any]]) -> Dweller:
        return await crud.dweller.update(
            db_session, dweller_id, DwellerUpdate(bio=compile_bio(entries), bio_entries=entries)
        )

    async def append_entry(
        self,
        db_session: AsyncSession,
        dweller_id: UUID4,
        source: str,
        text: str,
        ref: dict[str, Any] | None = None,
    ) -> Dweller:
        """Append one entry and recompile the rendered bio."""
        dweller = await crud.dweller.get(db_session, dweller_id)
        return await self._persist(db_session, dweller_id, self.with_entry(dweller, source, text, ref))

    async def record_visit(self, db_session: AsyncSession, dweller_id: UUID4, place_name: str) -> Dweller:
        """Record a first visit to a place; repeat visits are a no-op."""
        dweller = await crud.dweller.get(db_session, dweller_id)
        for entry in dweller.bio_entries or []:
            if entry.get("source") == "exploration" and (entry.get("ref") or {}).get("place") == place_name:
                return dweller
        entries = self.with_entry(dweller, "exploration", f"Visited {place_name}.", {"place": place_name})
        return await self._persist(db_session, dweller_id, entries)


bio_service = BioService()
