"""Asset manifest: provenance + validation overlay for generated assets.

The manifest is a curated registry of AI-generated assets (and, later, any
asset that needs provenance metadata). It is NOT a replacement for the
name-to-file resolver dicts in ``app/utils/*_assets.py`` — those encode
fallback semantics the manifest cannot express. Resolvers consult the manifest
first and fall through to their existing logic when nothing is registered.
"""

import functools
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.core.enums import AssetRole, ReviewStatus

MANIFEST_PATH = Path(__file__).parent.parent / "data" / "assets" / "manifest.json"
STATIC_DIR = Path(__file__).parent.parent / "static"

_APPROVED_STATUSES = frozenset({ReviewStatus.REVIEWED, ReviewStatus.APPROVED})


class SceneActorAnchor(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    x: int
    y: int
    facing: Literal["left", "right"]
    scale: float = 1.0


class SceneGeometry(BaseModel):
    model_config = ConfigDict(frozen=True)

    camera: str
    safe_crop: tuple[int, int, int, int]
    floor_baseline_y: int
    actor_slots: tuple[SceneActorAnchor, ...]


class ActorLayerSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    slot: Literal["body", "face", "hair", "outfit", "weapon"]
    path: str
    z: int
    anchor_x: int
    anchor_y: int
    width: int
    height: int


class ActorGeometry(BaseModel):
    model_config = ConfigDict(frozen=True)

    canvas_width: int
    canvas_height: int
    baseline_y: int
    layers: tuple[ActorLayerSpec, ...]


class AssetRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    role: AssetRole
    catalog_key: str
    source: str
    workflow: str | None
    model: str | None
    prompt_ref: str | None
    seed: int | None
    path: str
    width: int
    height: int
    format: str
    has_alpha: bool
    tiling: bool = False
    review_status: ReviewStatus
    ui_placement: str
    scene: SceneGeometry | None = None
    actor: ActorGeometry | None = None


@functools.lru_cache(maxsize=1)
def load_asset_records() -> tuple[AssetRecord, ...]:
    """Load and validate the manifest, cached for the process lifetime."""
    with MANIFEST_PATH.open("r", encoding="utf-8") as file:
        return tuple(AssetRecord.model_validate(record) for record in json.load(file))


def _disk_path(asset_path: str) -> Path:
    return STATIC_DIR / asset_path.removeprefix("/static/")


@functools.lru_cache(maxsize=1)
def _resolved_index() -> dict[tuple[AssetRole, str], AssetRecord]:
    """Servable records keyed by ``(role, catalog_key)``, resolved once.

    A record is servable when its review status is reviewed/approved and its
    file exists on disk. The existence check runs when this index is built, not
    on every lookup, so serialization paths never stat the filesystem. The
    manifest test keeps ``(role, catalog_key)`` unique, so selection is
    unambiguous; the first servable record wins if duplicates ever appear.
    """
    index: dict[tuple[AssetRole, str], AssetRecord] = {}
    for record in load_asset_records():
        if record.review_status not in _APPROVED_STATUSES:
            continue
        if not _disk_path(record.path).is_file():
            continue
        index.setdefault((record.role, record.catalog_key), record)
    return index


def resolve_record(role: AssetRole, catalog_key: str) -> AssetRecord | None:
    """The single servable manifest record for *role* + *catalog_key*, if any.

    Selection and the review/on-disk gate are atomic: callers get the exact
    record whose path was validated, so they can read ``scene``/``actor``
    geometry without a second lookup that could disagree.
    """
    return _resolved_index().get((role, catalog_key))


def manifest_url(role: AssetRole, catalog_key: str) -> str | None:
    """Return the manifest path for *role* + *catalog_key*, if a usable record exists."""
    record = resolve_record(role, catalog_key)
    return record.path if record is not None else None


def reset_asset_manifest() -> None:
    """Clear cached manifest state (for tests that rewrite the manifest file)."""
    load_asset_records.cache_clear()
    _resolved_index.cache_clear()
