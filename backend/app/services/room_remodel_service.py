"""Free room layout changes that preserve resources and resident assignments."""

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core import db_locks
from app.crud.incident import incident_crud
from app.models.room import Room
from app.services.room_assignment_policy import room_occupancy_lock_key, vault_placement_lock_key
from app.utils.exceptions import ResourceConflictException, VaultOperationException
from app.utils.room_assets import get_room_image_url
from app.utils.room_rules import room_refund


def _validate_remodelable(room: Room) -> tuple[int, int]:
    size = room.size or room.size_min
    if room.is_unique or room.size_max <= room.size_min or size % room.size_min:
        raise VaultOperationException(detail="This room cannot be split or merged.")
    if room.coordinate_x is None or room.coordinate_y is None:
        raise VaultOperationException(detail="This room has no grid position.")
    return room.coordinate_x, room.coordinate_y


def _share(total: int | None, count: int, index: int) -> int | None:
    if total is None:
        return None
    quotient, remainder = divmod(total, count)
    return quotient + (index < remainder)


async def remodel_room(db_session: AsyncSession, room_id: UUID4, other_room_id: UUID4 | None = None) -> list[Room]:
    """Split into base segments, or merge exactly two explicitly selected neighbors."""
    source = await crud.room.get(db_session, room_id)
    async with db_locks.hold_advisory_lock(db_session, vault_placement_lock_key(source.vault_id)) as acquired:
        if not acquired:
            raise ResourceConflictException(detail="Vault layout is busy — try again.")
        await db_session.refresh(source)
        source_x, _ = _validate_remodelable(source)
        rooms = [source]
        if other_room_id is not None:
            other = await crud.room.get(db_session, other_room_id)
            await db_session.refresh(other)
            _validate_remodelable(other)
            rooms.append(other)
        # Spawn/spread use this transaction lock too: no incident may start after our check.
        if not await db_locks.try_advisory_xact_lock(db_session, f"incident-spawn:{source.vault_id}"):
            raise ResourceConflictException(detail="Incident state is changing — try again.")
        ids = {room.id for room in rooms}
        for incident in await incident_crud.get_active_by_vault(db_session, source.vault_id):
            if incident.room_id in ids or {str(room_id) for room_id in ids}.intersection(incident.rooms_affected or []):
                raise VaultOperationException(detail="Resolve the incident before changing these rooms.")

        for room_id_to_lock in sorted(ids, key=str):
            await db_locks.advisory_xact_lock(db_session, room_occupancy_lock_key(room_id_to_lock))
        dwellers = list(await crud.room.get_remodel_dwellers(db_session, source.vault_id, list(ids)))
        if other_room_id is None:
            count = source.segment_count
            if count < 2:
                raise VaultOperationException(detail="This room already occupies one base segment.")
            values = source.model_dump(exclude={"id", "created_at", "updated_at"})
            refund = room_refund(source)
            replacements = [
                Room.model_validate(
                    values
                    | {
                        "coordinate_x": source_x + index * source.size_min,
                        "size": source.size_min,
                        "capacity": _share(source.capacity, count, index),
                        "output": _share(source.output, count, index),
                        "refund_caps": _share(refund, count, index),
                        "image_url": get_room_image_url(
                            source.name, tier=source.tier, size=source.size_min, style=source.room_style
                        ),
                    }
                )
                for index in range(count)
            ]
            # Keep the left segment's identity for reports and dispatch provenance.
            replacements[0].id = source.id
            destinations = {}
            # Distribute workers and apprentices separately to retain per-segment slots.
            for mature in (True, False):
                group = sorted((d for d in dwellers if d.is_mature == mature), key=lambda d: str(d.id))
                destinations.update({d.id: replacements[i % count].id for i, d in enumerate(group)})
        else:
            rooms.sort(key=lambda room: room.coordinate_x or 0)
            left, right = rooms
            total_size = (left.size or left.size_min) + (right.size or right.size_min)
            if (
                left.id == right.id
                or any(
                    getattr(left, field) != getattr(right, field)
                    for field in ("vault_id", "name", "tier", "coordinate_y", "size_min", "room_style")
                )
                or (left.coordinate_x or 0) + (left.size or left.size_min) != right.coordinate_x
                or total_size > min(left.size_max, right.size_max)
            ):
                raise VaultOperationException(
                    detail="Choose adjacent rooms of the same type and tier within the size limit."
                )
            values = left.model_dump(exclude={"created_at", "updated_at"})
            replacements = [
                Room.model_validate(
                    values
                    | {
                        "size": total_size,
                        "capacity": None
                        if left.capacity is None and right.capacity is None
                        else (left.capacity or 0) + (right.capacity or 0),
                        "output": None
                        if left.output is None and right.output is None
                        else (left.output or 0) + (right.output or 0),
                        "refund_caps": sum(room_refund(room) for room in rooms),
                        "image_url": get_room_image_url(
                            left.name, tier=left.tier, size=total_size, style=left.room_style
                        ),
                    }
                )
            ]
            destinations = {d.id: left.id for d in dwellers}
        return await crud.room.apply_remodel(db_session, rooms, replacements, destinations)
