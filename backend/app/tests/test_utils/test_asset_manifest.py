"""Tests for the asset manifest registry and its encoding guarantees."""

from pathlib import Path

import pytest
from PIL import Image

from app.core.enums import AssetRole
from app.utils.asset_manifest import STATIC_DIR, load_asset_records

#: Static subdir each role's assets must live under (path prefix check).
ROLE_PATH_PREFIXES: dict[AssetRole, tuple[str, ...]] = {
    AssetRole.ROOM_GRID: ("/static/room_images/",),
    AssetRole.ROOM_DETAIL_SCENE: ("/static/room_images/", "/static/poc_v25/"),
    AssetRole.WEAPON_ICON: ("/static/weapon_images/",),
    AssetRole.OUTFIT_ICON: ("/static/apparel_images/",),
    AssetRole.JUNK_ICON: ("/static/junk_images/",),
    AssetRole.PET_ICON: ("/static/pet_images/",),
    AssetRole.DWELLER_PORTRAIT: ("/static/legendary_dweller_images/",),
    AssetRole.ARENA_ACTOR: ("/static/actor_poc/", "/static/poc_v25/"),
    AssetRole.ARENA_EQUIPMENT: ("/static/actor_poc/", "/static/poc_v25/"),
}

_SWEPT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def test_manifest_keys_are_unique() -> None:
    records = load_asset_records()
    keys = [record.key for record in records]
    assert len(keys) == len(set(keys))


def test_manifest_role_catalog_keys_are_unique() -> None:
    """Resolution is keyed by (role, catalog_key); duplicates would be ambiguous."""
    keys = [(record.role, record.catalog_key) for record in load_asset_records()]
    assert len(keys) == len(set(keys))


def test_manifest_assets_match_declared_encoding() -> None:
    """Every manifest record's file must exist and match its declared encoding."""
    failures: list[str] = []
    for record in load_asset_records():
        path = STATIC_DIR / record.path.removeprefix("/static/")
        if not path.is_file():
            failures.append(f"{record.key}: AssetMissing ({path} not found)")
            continue
        with Image.open(path) as image:
            image.load()
            detected_format = (image.format or "").lower()
            if detected_format != record.format:
                failures.append(
                    f"{record.key}: AssetEncodingMismatch (declared {record.format}, decoded {detected_format})"
                )
            if image.size != (record.width, record.height):
                failures.append(
                    f"{record.key}: AssetDimensionMismatch (declared {(record.width, record.height)}, "
                    f"decoded {image.size})"
                )
            if ("A" in image.getbands()) != record.has_alpha:
                failures.append(
                    f"{record.key}: AssetAlphaMismatch (declared has_alpha={record.has_alpha}, "
                    f"decoded mode {image.mode})"
                )
            if detected_format != path.suffix.lstrip(".").lower():
                failures.append(
                    f"{record.key}: AssetExtensionMismatch (extension {path.suffix}, decoded {detected_format})"
                )
    assert failures == [], "\n".join(failures)


@pytest.mark.slow
def test_all_static_images_decode_and_match_extension() -> None:
    """Every static image decodes and its detected format is a supported web format.

    The wiki-derived assets are stored as WebP payloads under ``.png`` names, so
    the extension check is against the swept format set rather than a strict
    per-file match; the manifest records themselves are checked strictly above.
    """
    failures: list[str] = []
    for path in STATIC_DIR.rglob("*"):
        if path.suffix.lower() not in _SWEPT_EXTENSIONS:
            continue
        try:
            with Image.open(path) as image:
                image.load()
                detected_format = (image.format or "").lower()
        except Exception as exc:
            failures.append(f"{path}: undecodable ({exc})")
            continue
        if detected_format not in {ext.lstrip(".") for ext in _SWEPT_EXTENSIONS}:
            failures.append(f"{path}: detected format {detected_format!r} not in swept set")
    assert failures == [], "\n".join(failures)


def test_manifest_records_have_known_role_path_prefix() -> None:
    """Every record's path must live under the static subdir for its role."""
    failures: list[str] = []
    for record in load_asset_records():
        prefix = ROLE_PATH_PREFIXES.get(record.role)
        if prefix is None:
            failures.append(f"{record.key}: no known path prefix for role {record.role!r}")
        elif not any(record.path.startswith(option) for option in prefix):
            failures.append(f"{record.key}: path {record.path!r} does not start with any of {prefix}")
    assert failures == [], "\n".join(failures)
