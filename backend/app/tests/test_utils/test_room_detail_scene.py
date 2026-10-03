"""Tests for catalog-driven room detail scenes (issue #819)."""

from uuid import uuid4

from app.core.enums import AssetRole, RoomTypeEnum
from app.models.room import Room
from app.schemas.room import RoomRead
from app.utils.asset_manifest import load_asset_records
from app.utils.room_assets import get_room_detail_scene


def _arena_record():
    return next(
        record
        for record in load_asset_records()
        if record.role == AssetRole.ROOM_DETAIL_SCENE and record.catalog_key == "Arena"
    )


def test_arena_resolves_detail_scene_from_manifest() -> None:
    record = _arena_record()
    assert record.scene is not None

    scene = get_room_detail_scene("Arena")

    assert scene is not None
    assert scene.image_url == record.path
    assert (scene.width, scene.height) == (record.width, record.height)
    assert scene.camera == record.scene.camera
    assert scene.safe_crop == record.scene.safe_crop
    assert scene.floor_baseline_y == record.scene.floor_baseline_y
    assert [(slot.id, slot.x, slot.y, slot.facing, slot.scale) for slot in scene.actor_slots] == [
        (slot.id, slot.x, slot.y, slot.facing, slot.scale) for slot in record.scene.actor_slots
    ]


def test_unregistered_room_resolves_none() -> None:
    assert get_room_detail_scene("Power Generator") is None


def _make_room(name: str) -> Room:
    return Room(
        id=uuid4(),
        vault_id=uuid4(),
        name=name,
        category=RoomTypeEnum.MISC,
        base_cost=1000,
        size_min=3,
        size_max=9,
        size=3,
        tier=1,
    )


def test_room_read_exposes_detail_scene() -> None:
    read = RoomRead.model_validate(_make_room("Arena"), from_attributes=True)

    assert read.detail_scene is not None
    assert read.detail_scene.image_url == _arena_record().path
    assert read.detail_scene.actor_slots[0].id == "actor_a"


def test_room_read_detail_scene_none_without_manifest_record() -> None:
    read = RoomRead.model_validate(_make_room("Power Generator"), from_attributes=True)

    assert read.detail_scene is None
