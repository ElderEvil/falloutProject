"""Pre-generation service for dev/QA dweller seeding.

Owns the deterministic template-based bio workflow: creating random
dwellers, composing bios from origin + visited places, and registering the
resulting world-map markers. CLI commands are thin wrappers over this
service (AGENTS.md: business logic lives in services, not CLI scripts).
"""

from __future__ import annotations

import logging
import random as std_random
from dataclasses import dataclass

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.schemas.dweller import DwellerUpdate
from app.services.exploration.data_loader import load_discovery_names
from app.services.map_service import map_service
from app.utils.places import GENERIC_ORIGIN_SKIP, normalize_place_name

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# bio templates — cheap, deterministic, NO LLM
# ------------------------------------------------------------------

ADULT_BIO_TEMPLATES: list[str] = [
    "Grew up in {origin}. {first_name} spent years wandering the wastes{visited_str} before finding this vault.",
    "Originally from {origin}, {first_name} roamed{visited_str} seeking shelter. The wasteland left its mark.",
    "A child of {origin}, {first_name} survived the trek{visited_str}. Every step was a lesson in endurance.",
    "{origin} native. {first_name} earned a reputation scavenging{visited_str} before joining the vault community.",
    "Born near {origin}, {first_name} travelled{visited_str} during the Great Storm. Survival was uncertain.",
    "Hails from the outskirts of {origin}. {first_name} wandered{visited_str} on the long road to safety.",
    "The ruins of {origin} were {first_name}'s first home. They explored{visited_str} before the vault took them in.",
    "A wanderer from {origin}. {first_name} traded stories with survivors{visited_str} along the way.",
]

MAX_PICK_ATTEMPTS = 50
NAME_MAX_LEN = 64


@dataclass(frozen=True)
class PregenResult:
    """Per-dweller outcome of a pre-generation run (for CLI reporting)."""

    dweller_id: UUID4
    first_name: str
    last_name: str | None
    origin_place: str
    visited_count: int
    bio_length: int


# ------------------------------------------------------------------
# pure helpers (testable, no I/O)
# ------------------------------------------------------------------


def _clean_name(name: str) -> str:
    """Strip whitespace and clamp to NAME_MAX_LEN characters."""
    return name.strip()[:NAME_MAX_LEN]


def _pick_place(
    rng: std_random.Random,
    prefixes: list[str],
    suffixes: list[str],
) -> str:
    """Pick a random prefix-suffix combo, avoiding GENERIC_ORIGIN_SKIP tokens."""
    for _ in range(MAX_PICK_ATTEMPTS):
        raw = f"{rng.choice(prefixes)} {rng.choice(suffixes)}"
        if normalize_place_name(raw) not in GENERIC_ORIGIN_SKIP:
            return _clean_name(raw)
    # Exhausted attempts — return a safe fallback
    return _clean_name(f"{rng.choice(prefixes)} {rng.choice(suffixes)}")


def _format_visited_str(places: list[str]) -> str:
    """Format a list of place names into a grammatically correct inline phrase.

    Returns an empty string for zero places, or a leading-", " phrase like
    ", passing through the Rusty Shack" or ", passing through Rusty Shack, Abandoned Depot, and Glowing Silo".
    """
    if not places:
        return ""
    joined = " and ".join(places) if len(places) <= 2 else ", ".join(places[:-1]) + ", and " + places[-1]
    return f", passing through {joined}"


def _compose_bio(
    rng: std_random.Random,
    first_name: str,
    origin: str,
    visited: list[str],
) -> str:
    """Pick a random template and render it with the dweller's origin + visited places."""
    template = rng.choice(ADULT_BIO_TEMPLATES)
    visited_str = _format_visited_str(visited)
    return template.format(first_name=first_name, origin=origin, visited_str=visited_str)


class PregenService:
    """Deterministic dweller + bio + world-map seeding workflows."""

    @staticmethod
    async def _ensure_vault_exists(db_session: AsyncSession, vault_id: UUID4) -> None:
        """Raise ResourceNotFoundException if the vault does not exist."""
        await crud.vault.get(db_session, id=vault_id)

    @staticmethod
    def _load_name_pools() -> tuple[list[str], list[str]]:
        name_pools = load_discovery_names()
        return name_pools["prefixes"], name_pools["suffixes"]

    async def pregen_dwellers(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        count: int,
        seed: int | None = None,
        origin: str | None = None,
    ) -> list[PregenResult]:
        """Create ``count`` random dwellers with deterministic bios + map markers.

        Each dweller gets a cheap template-based bio that mentions an origin
        settlement and 0-3 visited places. Place names are drawn from the
        exploration discovery-name pools and registered on the world map so the
        frontend bio-linkify feature lights up immediately.

        When ``seed`` is provided the whole run (names, stats, bio, places) is
        reproducible. Intended for dev/QA seeding — no LLM calls, no quota
        consumption, cheap.
        """
        await self._ensure_vault_exists(db_session, vault_id)
        rng = std_random.Random(seed)
        prefixes, suffixes = self._load_name_pools()

        results: list[PregenResult] = []
        for _ in range(count):
            dweller = await crud.dweller.create_random(
                db_session, vault_id=vault_id, seed=seed, register_bio_places=False
            )

            origin_place = _clean_name(origin) if origin else _pick_place(rng, prefixes, suffixes)
            visited_count = rng.randint(0, 3)
            visited_places = [_pick_place(rng, prefixes, suffixes) for _ in range(visited_count)]

            bio = _compose_bio(rng, dweller.first_name, origin_place, visited_places)

            await crud.dweller.update(db_session, id=dweller.id, obj_in=DwellerUpdate(bio=bio))

            await map_service.register_bio_places(
                db_session=db_session,
                dweller=dweller,
                origin_place=origin_place,
                visited_places=visited_places,
                explicit_origin=origin,
            )

            results.append(
                PregenResult(
                    dweller_id=dweller.id,
                    first_name=dweller.first_name,
                    last_name=dweller.last_name,
                    origin_place=origin_place,
                    visited_count=visited_count,
                    bio_length=len(bio),
                )
            )
        return results

    async def fill_missing_bios(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        *,
        count: int = 0,
        seed: int | None = None,
        origin: str | None = None,
        force: bool = False,
    ) -> list[PregenResult]:
        """Fill missing (or forced) bios for existing dwellers in a vault."""
        await self._ensure_vault_exists(db_session, vault_id)
        rng = std_random.Random(seed)
        prefixes, suffixes = self._load_name_pools()

        # Existing dwellers, newest first (deterministic order)
        dwellers = await crud.dweller.get_multi_by_vault(
            db_session,
            vault_id=vault_id,
            sort_by="created_at",
            order="desc",
        )
        eligible = [d for d in dwellers if force or not d.bio]
        if count > 0:
            eligible = eligible[:count]

        results: list[PregenResult] = []
        for dweller in eligible:
            origin_place = _clean_name(origin) if origin else _pick_place(rng, prefixes, suffixes)
            visited_count = rng.randint(0, 3)
            visited_places = [_pick_place(rng, prefixes, suffixes) for _ in range(visited_count)]

            bio = _compose_bio(rng, dweller.first_name, origin_place, visited_places)

            await crud.dweller.update(db_session, id=dweller.id, obj_in=DwellerUpdate(bio=bio))

            await map_service.register_bio_places(
                db_session=db_session,
                dweller=dweller,
                origin_place=origin_place,
                visited_places=visited_places,
                explicit_origin=origin,
            )

            results.append(
                PregenResult(
                    dweller_id=dweller.id,
                    first_name=dweller.first_name,
                    last_name=dweller.last_name,
                    origin_place=origin_place,
                    visited_count=visited_count,
                    bio_length=len(bio),
                )
            )
        return results


pregen_service = PregenService()
