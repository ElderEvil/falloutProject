"""Vault economy: resource production, medical transfer, capacity, and caps.

Public operations are called through ``VaultService`` in
``app.services.vault_service``; each operation owns its transaction inside this
module (or defers it, where noted, for a caller-owned commit).
"""

import logging

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import RoomActionEnum, RoomTypeEnum, SPECIALEnum
from app.crud import dweller as dweller_crud
from app.crud import vault as vault_crud
from app.crud.storage import storage as storage_crud
from app.models import Room, Storage, Vault
from app.options.races import can_use_radaway
from app.schemas.vault import MedicalTransferResponse, VaultUpdate
from app.services.resource_manager import ResourceManager
from app.utils.exceptions import (
    InsufficientResourcesException,
    ResourceConflictException,
    ResourceNotFoundException,
)

logger = logging.getLogger(__name__)

resource_manager = ResourceManager()


async def update_vault_resources(db_session: AsyncSession, vault_id: UUID4) -> Vault:
    """Update vault resources based on resource manager processing."""
    updated_resources, events = await resource_manager.process_vault_resources(
        db_session=db_session, vault_id=vault_id, seconds_passed=60
    )
    vault_obj = await vault_crud.update(db_session=db_session, id=vault_id, obj_in=updated_resources)
    await resource_manager.emit_production_events(vault_id, events)
    return vault_obj


async def stage_medical_supply_transfer(
    db_session: AsyncSession,
    vault: Vault,
    dweller_id: UUID4,
    stimpaks: int,
    radaways: int,
) -> MedicalTransferResponse:
    """Validate and stage a vault -> dweller medical transfer without committing.

    Composable no-commit medical-stock operation: the caller owns the commit
    boundary (``transfer_medical_supplies`` for the storage endpoint). Raises on
    validation failures; nothing is persisted here.
    """
    storage = await storage_crud.get_by_vault(db_session, vault.id)
    if not storage:
        raise ResourceNotFoundException(model=Storage, identifier=vault.id)

    vault_stimpaks = storage.stimpack or 0
    vault_radaways = storage.radaway or 0

    if stimpaks > vault_stimpaks:
        raise ResourceConflictException(detail=f"Vault only has {vault_stimpaks} stimpaks")
    if radaways > vault_radaways:
        raise ResourceConflictException(detail=f"Vault only has {vault_radaways} radaways")

    dweller = await dweller_crud.get(db_session, dweller_id)

    if dweller.vault_id != vault.id:
        from app.utils.exceptions import AccessDeniedException

        raise AccessDeniedException(detail="Dweller does not belong to this vault")

    if radaways > 0 and not can_use_radaway(dweller):
        raise ResourceConflictException(detail="This dweller cannot carry RadAway.")

    dweller_stimpaks = dweller.stimpack or 0
    dweller_radaways = dweller.radaway or 0

    max_per_dweller = 15
    if stimpaks + dweller_stimpaks > max_per_dweller:
        raise ResourceConflictException(detail=f"Dweller can only carry {max_per_dweller} stimpaks")
    if radaways + dweller_radaways > max_per_dweller:
        raise ResourceConflictException(detail=f"Dweller can only carry {max_per_dweller} radaways")

    new_storage_stimpaks = vault_stimpaks - stimpaks
    new_storage_radaways = vault_radaways - radaways
    new_dweller_stimpaks = dweller_stimpaks + stimpaks
    new_dweller_radaways = dweller_radaways + radaways

    storage.stimpack = new_storage_stimpaks
    storage.radaway = new_storage_radaways
    db_session.add(storage)

    await dweller_crud.update(
        db_session,
        dweller_id,
        obj_in={"stimpack": new_dweller_stimpaks, "radaway": new_dweller_radaways},
        commit=False,
    )

    return MedicalTransferResponse(
        vault_stimpaks=new_storage_stimpaks,
        vault_radaways=new_storage_radaways,
        dweller_stimpaks=new_dweller_stimpaks,
        dweller_radaways=new_dweller_radaways,
    )


async def transfer_medical_supplies(
    db_session: AsyncSession,
    vault: Vault,
    dweller_id: UUID4,
    stimpaks: int,
    radaways: int,
) -> MedicalTransferResponse:
    """Transfer medical supplies from vault storage to a dweller's inventory.

    Dwellers can carry max 15 stimpaks and 15 radaways each.
    """
    response = await stage_medical_supply_transfer(db_session, vault, dweller_id, stimpaks, radaways)
    try:
        await db_session.commit()
    except Exception:
        await db_session.rollback()
        raise

    logger.info(
        "Medical supplies transferred",
        extra={
            "vault_id": str(vault.id),
            "dweller_id": str(dweller_id),
            "stimpaks_transferred": stimpaks,
            "radaways_transferred": radaways,
        },
    )

    return response


def calculate_new_capacity(
    action: RoomActionEnum,
    current_capacity: int | None,
    room_capacity: int | None,
    previous_capacity: int | None = None,
) -> int:
    base = current_capacity or 0
    if room_capacity is None:
        return base

    # A replacement (upgrade, or a merge absorbing an already-counted room)
    # swaps the room's own contribution, so only the change counts.
    if previous_capacity is not None:
        return base - previous_capacity + room_capacity
    if action in {RoomActionEnum.BUILD, RoomActionEnum.UPGRADE}:
        return base + room_capacity
    if action == RoomActionEnum.DESTROY:
        return base - room_capacity
    msg = f"Invalid room action: {action}"
    raise ValueError(msg)


async def recalculate_vault_attributes(
    *,
    db_session: AsyncSession,
    vault_obj: Vault,
    room_obj: Room,
    action: RoomActionEnum,
    previous_capacity: int | None = None,
) -> Vault:
    """Recalculate the vault attributes based on the newly added or removed room."""
    if room_obj.category == RoomTypeEnum.PRODUCTION and room_obj.capacity is not None:
        await handle_production_room(db_session, vault_obj, room_obj, action, previous_capacity)
    elif room_obj.category == RoomTypeEnum.CAPACITY:
        await handle_capacity_room(db_session, vault_obj, room_obj, action, previous_capacity)

    return vault_obj


async def handle_production_room(
    db_session: AsyncSession,
    vault_obj: Vault,
    room_obj: Room,
    action: RoomActionEnum,
    previous_capacity: int | None = None,
) -> None:
    """Handle production room capacity updates."""
    if room_obj.ability not in (
        SPECIALEnum.STRENGTH,
        SPECIALEnum.AGILITY,
        SPECIALEnum.PERCEPTION,
        SPECIALEnum.INTELLIGENCE,
    ):
        msg = f"Invalid room ability: {room_obj.ability}"
        raise ValueError(msg)

    resource_map = {
        SPECIALEnum.STRENGTH: ("power_max", vault_obj.power_max),
        SPECIALEnum.AGILITY: ("food_max", vault_obj.food_max),
        SPECIALEnum.PERCEPTION: ("water_max", vault_obj.water_max),
        SPECIALEnum.INTELLIGENCE: (None, None),
    }

    field, current = resource_map[room_obj.ability]

    if field:
        new_capacity = calculate_new_capacity(action, current, room_obj.capacity, previous_capacity)
        await vault_crud.update(db_session=db_session, id=vault_obj.id, obj_in={field: new_capacity}, commit=False)
        await db_session.commit()


async def handle_capacity_room(
    db_session: AsyncSession,
    vault_obj: Vault,
    room_obj: Room,
    action: RoomActionEnum,
    previous_capacity: int | None = None,
) -> None:
    """Handle capacity room updates."""
    if room_obj.ability == SPECIALEnum.CHARISMA:
        new_population_max = calculate_new_capacity(
            action, vault_obj.population_max or 0, room_obj.capacity, previous_capacity
        )
        await vault_crud.update(db_session, vault_obj.id, VaultUpdate(population_max=new_population_max))
    elif room_obj.ability == SPECIALEnum.ENDURANCE and room_obj.capacity is not None:
        storage_obj = await storage_crud.get_by_vault(db_session, vault_obj.id)

        if storage_obj is None:
            storage_obj = await storage_crud.create_for_vault(db_session=db_session, vault_id=vault_obj.id)

        current_max_space = storage_obj.max_space
        new_storage_space_max = calculate_new_capacity(action, current_max_space, room_obj.capacity, previous_capacity)
        await storage_crud.set_max_space(db_session, vault_obj.id, new_storage_space_max)


async def is_enough_dwellers(*, db_session: AsyncSession, vault_id: UUID4, population_required: int | None) -> bool:
    """Check if the vault has enough dwellers to perform an operation."""
    if population_required is None:
        return True
    dwellers_count = await vault_crud.get_population(db_session=db_session, vault_id=vault_id)
    return dwellers_count >= population_required


async def is_enough_population_space(*, db_session: AsyncSession, vault_id: UUID4, space_required: int) -> bool:
    """Check if the vault has enough space to perform an operation.

    Only counts dwellers that are assigned to rooms (have room_id).
    Unassigned dwellers don't take up living space.
    """
    population_max, current_assigned_population = await vault_crud.get_population_space(
        db_session=db_session, vault_id=vault_id
    )
    if population_max is None:
        if current_assigned_population == 0:
            raise ResourceNotFoundException(Vault, identifier=vault_id)
        return False
    return current_assigned_population + space_required <= population_max


async def deposit_caps(
    *,
    db_session: AsyncSession,
    vault_obj: Vault,
    amount: int,
    commit: bool = True,
    emit_event: bool = True,
    track_earnings: bool = True,
) -> int:
    """Deposit the specified amount to the vault's bottle caps as part of a revenue operation.

    Returns the amount actually credited (less than requested when the cap is hit).
    """
    capped = min(vault_obj.bottle_caps + amount, 999_999)
    credited = capped - vault_obj.bottle_caps
    await vault_crud.update(db_session, id=vault_obj.id, obj_in=VaultUpdate(bottle_caps=capped), commit=commit)

    if track_earnings:
        from app.services.user_service import user_service

        await user_service.record_vault_statistic(
            db_session,
            vault_obj.id,
            "total_caps_earned",
            credited,
            commit=commit,
        )

    if emit_event:
        from app.core.event_bus import GameEvent, event_bus

        await event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault_obj.id, {"resource_type": "caps", "amount": credited})

    return credited


async def withdraw_caps(*, db_session: AsyncSession, vault_obj: Vault, amount: int, commit: bool = True) -> None:
    """Withdraw the specified amount from the vault's bottle caps as part of a spending operation.

    Pass ``commit=False`` to compose the deduction with other writes into one transaction.
    """
    if vault_obj.bottle_caps < amount:
        amount_needed = amount - vault_obj.bottle_caps
        raise InsufficientResourcesException(resource_name="bottle caps", resource_amount=amount_needed)
    await vault_crud.update(
        db_session,
        id=vault_obj.id,
        obj_in=VaultUpdate(bottle_caps=vault_obj.bottle_caps - amount),
        commit=commit,
    )
