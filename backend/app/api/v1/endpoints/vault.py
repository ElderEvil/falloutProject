from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser, get_user_vault_or_403
from app.db.session import get_async_session
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.common import DwellerStatusEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerUpdate
from app.schemas.vault import VaultCreate, VaultNumber, VaultReadWithNumbers, VaultReadWithUser, VaultUpdate
from app.services.vault_service import vault_service

router = APIRouter()


@router.post("/", response_model=Vault, status_code=201)
async def create_vault(
    *,
    vault_data: VaultCreate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    admin: CurrentSuperuser,
):
    return await crud.vault.create_with_user_id(db_session=db_session, obj_in=vault_data, user_id=admin.id)


@router.get("/", response_model=list[VaultReadWithUser])
async def read_vault_list(
    *,
    skip: int = 0,
    limit: int = 100,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
):
    return await crud.vault.get_multi(db_session, skip=skip, limit=limit)


@router.get("/my", response_model=list[VaultReadWithNumbers])
async def read_my_vaults(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
):
    return await crud.vault.get_vaults_with_room_and_dweller_count(db_session=db_session, user_id=user.id)


@router.get("/{vault_id}", response_model=VaultReadWithNumbers)
async def read_vault(
    *,
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
):
    vault = await crud.vault.get(db_session, vault_id)
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")

    # Only allow users to view their own vaults, unless they're superuser
    if vault.user_id != user.id and not user.is_superuser:
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")

    return await crud.vault.get_vault_with_room_and_dweller_count(db_session=db_session, vault_id=vault_id)


@router.put("/{vault_id}", response_model=VaultReadWithUser)
async def update_vault(
    *,
    vault_id: UUID4,
    vault_data: VaultUpdate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
):
    vault = await crud.vault.get(db_session, vault_id)
    if vault.user_id != user.id or not user.is_superuser:
        raise HTTPException(status_code=403, detail="User does not have permission to update the vault")
    return await crud.vault.update(db_session, vault_id, vault_data)


@router.delete("/{vault_id}", status_code=204)
async def delete_vault(
    *,
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
    hard_delete: Annotated[bool, Query(description="If True, permanently delete. Otherwise soft delete.")] = False,
):
    """
    Delete a vault. By default performs soft delete to preserve data.
    Use hard_delete=True to permanently remove the vault.
    """
    vault = await crud.vault.get(db_session, vault_id)
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")
    if vault.user_id != user.id and not user.is_superuser:
        raise HTTPException(status_code=403, detail="User does not have permission to delete the vault")
    return await crud.vault.delete(db_session, vault_id, soft=not hard_delete)


@router.post("/{vault_id}/toggle_game_state", response_model=Vault, status_code=200)
async def toggle_game_state(
    *,
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentActiveUser,
):
    return await crud.vault.toggle_game_state(db_session=db_session, vault_id=vault_id)


@router.post("/initiate", response_model=Vault, status_code=201)
async def start_vault(
    *,
    vault_data: VaultNumber,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
):
    return await vault_service.initiate_vault(
        db_session=db_session, obj_in=vault_data, user_id=user.id, is_superuser=user.is_superuser
    )


@router.post("/update_resources", status_code=200)
async def update_vault_resources(
    *,
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
):
    return await vault_service.update_vault_resources(db_session=db_session, vault_id=vault_id)


@router.post("/{vault_id}/dwellers/unassign-all", response_model=dict[str, int])
async def unassign_all_dwellers(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Unassign all dwellers from their rooms in the specified vault."""
    from app.schemas.dweller import DwellerUpdate

    dwellers = await crud.dweller.get_multi_by_vault(db_session, vault_id=vault.id, limit=10000)
    unassigned_count = 0

    for dweller in dwellers:
        if dweller.room_id is not None:
            await crud.dweller.update(
                db_session,
                dweller.id,
                DwellerUpdate(room_id=None, status=DwellerStatusEnum.IDLE),
            )
            unassigned_count += 1

    return {"unassigned_count": unassigned_count}


@router.post("/{vault_id}/dwellers/auto-assign-production")
async def auto_assign_production_rooms(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    Intelligently assign unassigned dwellers to production rooms based on SPECIAL stats.

    Priority order: Power Plant (Strength) → Diner (Agility) → Water Treatment (Perception)
    Dwellers are matched to rooms based on their relevant SPECIAL stat (highest stat dwellers assigned first).
    """
    # Priority order for assignment
    priority_abilities = [
        SPECIALEnum.STRENGTH,  # Power plants
        SPECIALEnum.AGILITY,  # Diners
        SPECIALEnum.PERCEPTION,  # Water treatment
    ]

    # Map abilities to dweller stat attribute names
    ability_to_stat_map = {
        SPECIALEnum.STRENGTH: "strength",
        SPECIALEnum.AGILITY: "agility",
        SPECIALEnum.PERCEPTION: "perception",
    }

    # Get all production rooms in vault
    rooms_query = (
        select(Room)
        .where(Room.vault_id == vault.id)
        .where(Room.category == RoomTypeEnum.PRODUCTION)
        .where(Room.ability.in_(priority_abilities))
    )
    rooms_result = await db_session.execute(rooms_query)
    all_production_rooms = rooms_result.scalars().all()

    # Get all unassigned dwellers (room_id is None, not deleted, not dead)
    unassigned_query = (
        select(Dweller)
        .where(Dweller.vault_id == vault.id)
        .where(Dweller.room_id.is_(None))
        .where(Dweller.is_deleted == False)
        .where(Dweller.is_dead == False)
    )
    unassigned_result = await db_session.execute(unassigned_query)
    unassigned_dwellers = list(unassigned_result.scalars().all())

    assignments = []
    assigned_dweller_ids = set()

    for ability in priority_abilities:
        if not unassigned_dwellers:
            break

        # Get rooms with this ability
        ability_rooms = [r for r in all_production_rooms if r.ability == ability]

        for room in ability_rooms:
            if not unassigned_dwellers:
                break

            # Get current dweller count in room
            dweller_count_query = select(Dweller).where(Dweller.room_id == room.id)
            dweller_count_result = await db_session.execute(dweller_count_query)
            current_dwellers_in_room = len(dweller_count_result.scalars().all())

            # Calculate room capacity (2 dwellers per 3 size units)
            room_size = room.size if room.size is not None else room.size_min
            max_capacity = (room_size // 3) * 2 if room_size else 0

            available_slots = max_capacity - current_dwellers_in_room
            if available_slots <= 0:
                continue

            # Sort unassigned dwellers by the matching SPECIAL stat (descending)
            stat_name = ability_to_stat_map[ability]
            sorted_dwellers = sorted(
                [d for d in unassigned_dwellers if d.id not in assigned_dweller_ids],
                key=lambda d: getattr(d, stat_name),
                reverse=True,
            )

            # Assign dwellers to this room
            for dweller in sorted_dwellers[:available_slots]:
                await crud.dweller.update(
                    db_session,
                    dweller.id,
                    DwellerUpdate(room_id=room.id, status=DwellerStatusEnum.WORKING),
                )
                assignments.append(
                    {
                        "dweller_id": str(dweller.id),
                        "room_id": str(room.id),
                        "room_name": room.name,
                    }
                )
                assigned_dweller_ids.add(dweller.id)

        # Remove assigned dwellers from the list for next iteration
        unassigned_dwellers = [d for d in unassigned_dwellers if d.id not in assigned_dweller_ids]

    return {"assigned_count": len(assignments), "assignments": assignments}


@router.post("/{vault_id}/dwellers/auto-assign-all")
async def auto_assign_all_rooms(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    Intelligently assign unassigned dwellers to ALL room types based on SPECIAL stats.

    Priority order:
    1. Production rooms (Strength: Power, Perception: Water, Agility: Food) - most critical
    2. Utility rooms (Intelligence: Medbay/Science Lab, Charisma: Radio) - important services
    3. Training rooms (all 7 SPECIAL stats) - for development

    Dwellers are matched to rooms based on their relevant SPECIAL stat (highest stat dwellers assigned first).
    """
    # Complete ability to stat mapping for all 7 SPECIAL stats
    ability_to_stat_map = {
        SPECIALEnum.STRENGTH: "strength",
        SPECIALEnum.PERCEPTION: "perception",
        SPECIALEnum.ENDURANCE: "endurance",
        SPECIALEnum.CHARISMA: "charisma",
        SPECIALEnum.INTELLIGENCE: "intelligence",
        SPECIALEnum.AGILITY: "agility",
        SPECIALEnum.LUCK: "luck",
    }

    # Priority order: production abilities first, then utility, then training
    # Priority 1: Production rooms (S, P, A)
    production_abilities = [
        SPECIALEnum.STRENGTH,  # Power plants
        SPECIALEnum.PERCEPTION,  # Water treatment
        SPECIALEnum.AGILITY,  # Diners
    ]
    # Priority 2: Utility rooms (I, C)
    utility_abilities = [
        SPECIALEnum.INTELLIGENCE,  # Medbay & Science Lab
        SPECIALEnum.CHARISMA,  # Radio
    ]
    # Priority 3: Training rooms (all 7 stats including Luck)
    training_abilities = [
        SPECIALEnum.STRENGTH,
        SPECIALEnum.PERCEPTION,
        SPECIALEnum.ENDURANCE,
        SPECIALEnum.CHARISMA,
        SPECIALEnum.INTELLIGENCE,
        SPECIALEnum.AGILITY,
        SPECIALEnum.LUCK,
    ]

    # Get all rooms grouped by category
    rooms_query = (
        select(Room)
        .where(Room.vault_id == vault.id)
        .where(Room.category.in_([RoomTypeEnum.PRODUCTION, RoomTypeEnum.MISC, RoomTypeEnum.TRAINING]))
    )
    rooms_result = await db_session.execute(rooms_query)
    all_rooms = rooms_result.scalars().all()

    # Separate rooms by category
    production_rooms = [r for r in all_rooms if r.category == RoomTypeEnum.PRODUCTION]
    utility_rooms = [r for r in all_rooms if r.category == RoomTypeEnum.MISC]
    training_rooms = [r for r in all_rooms if r.category == RoomTypeEnum.TRAINING]

    # Get all unassigned dwellers (room_id is None, not deleted, not dead)
    unassigned_query = (
        select(Dweller)
        .where(Dweller.vault_id == vault.id)
        .where(Dweller.room_id.is_(None))
        .where(Dweller.is_deleted == False)
        .where(Dweller.is_dead == False)
    )
    unassigned_result = await db_session.execute(unassigned_query)
    unassigned_dwellers = list(unassigned_result.scalars().all())

    assignments = []
    assigned_dweller_ids = set()

    async def assign_to_rooms(rooms: list, abilities: list):
        """Helper function to assign dwellers to rooms based on abilities."""
        nonlocal unassigned_dwellers

        for ability in abilities:
            if not unassigned_dwellers:
                break

            # Get rooms with this ability
            ability_rooms = [r for r in rooms if r.ability == ability]

            for room in ability_rooms:
                if not unassigned_dwellers:
                    break

                # Get current dweller count in room
                dweller_count_query = select(Dweller).where(Dweller.room_id == room.id)
                dweller_count_result = await db_session.execute(dweller_count_query)
                current_dwellers_in_room = len(dweller_count_result.scalars().all())

                # Calculate room capacity (2 dwellers per 3 size units)
                room_size = room.size if room.size is not None else room.size_min
                max_capacity = (room_size // 3) * 2 if room_size else 0

                available_slots = max_capacity - current_dwellers_in_room
                if available_slots <= 0:
                    continue

                # Sort unassigned dwellers by the matching SPECIAL stat (descending)
                stat_name = ability_to_stat_map[ability]
                sorted_dwellers = sorted(
                    [d for d in unassigned_dwellers if d.id not in assigned_dweller_ids],
                    key=lambda d: getattr(d, stat_name),
                    reverse=True,
                )

                # Assign dwellers to this room
                for dweller in sorted_dwellers[:available_slots]:
                    await crud.dweller.update(
                        db_session,
                        dweller.id,
                        DwellerUpdate(room_id=room.id, status=DwellerStatusEnum.WORKING),
                    )
                    assignments.append(
                        {
                            "dweller_id": str(dweller.id),
                            "room_id": str(room.id),
                            "room_name": room.name,
                        }
                    )
                    assigned_dweller_ids.add(dweller.id)

            # Remove assigned dwellers from the list for next iteration
            unassigned_dwellers = [d for d in unassigned_dwellers if d.id not in assigned_dweller_ids]

    # Priority 1: Assign to production rooms first
    await assign_to_rooms(production_rooms, production_abilities)

    # Priority 2: Assign to utility/misc rooms
    await assign_to_rooms(utility_rooms, utility_abilities)

    # Priority 3: Assign to training rooms
    await assign_to_rooms(training_rooms, training_abilities)

    return {"assigned_count": len(assignments), "assignments": assignments}
