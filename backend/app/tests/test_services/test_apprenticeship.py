"""Regression tests for youth production apprenticeships."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app import crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.apprentice_scenario_service import apprentice_scenario_service
from app.services.breeding_service import BreedingService
from app.services.game_loop import game_loop_service
from app.services.training_service import TrainingService
from app.utils.exceptions import ValidationException


async def _create_youth(async_session: AsyncSession, vault: Vault, first_name: str) -> Dweller:
    return await crud.dweller.create(
        async_session,
        DwellerCreate(
            first_name=first_name,
            last_name="Apprentice",
            gender=GenderEnum.FEMALE,
            rarity=RarityEnum.COMMON,
            is_adult=False,
            age_group=AgeGroupEnum.TEEN,
            birth_date=datetime.utcnow(),
            vault_id=vault.id,
        ),
    )


async def _create_production_room(async_session: AsyncSession, vault: Vault):
    return await crud.room.create(
        async_session,
        RoomCreate(
            name="Power Generator",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.STRENGTH,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            capacity=4,
            output=1,
            size_min=1,
            size_max=3,
            size=3,
            vault_id=vault.id,
        ),
    )


@pytest.mark.asyncio
async def test_manual_youth_assignment_persists_room_ability_and_started_at(
    async_session: AsyncSession, vault: Vault
) -> None:
    youth = await _create_youth(async_session, vault, "Ada")
    room = await _create_production_room(async_session, vault)

    await crud.dweller.move_to_room(async_session, youth.id, room.id)

    await async_session.refresh(youth)
    assert youth.apprentice_stat == SPECIALEnum.STRENGTH
    assert youth.apprentice_started_at is not None


@pytest.mark.asyncio
async def test_only_one_youth_can_apprentice_in_a_production_room(async_session: AsyncSession, vault: Vault) -> None:
    first_youth = await _create_youth(async_session, vault, "Ada")
    second_youth = await _create_youth(async_session, vault, "Bea")
    room = await _create_production_room(async_session, vault)

    await crud.dweller.move_to_room(async_session, first_youth.id, room.id)

    with pytest.raises(ValidationException, match="already has an apprentice"):
        await crud.dweller.move_to_room(async_session, second_youth.id, room.id)


@pytest.mark.asyncio
async def test_overdue_apprenticeship_awards_once_and_resets_started_at(
    async_session: AsyncSession, vault: Vault
) -> None:
    youth = await _create_youth(async_session, vault, "Ada")
    room = await _create_production_room(async_session, vault)
    await crud.dweller.move_to_room(async_session, youth.id, room.id)
    youth.strength = 2
    duration = TrainingService.calculate_training_duration(youth.strength, room.tier)
    youth.apprentice_started_at = datetime.utcnow() - timedelta(seconds=duration * 2)
    await async_session.commit()

    result = await game_loop_service._process_apprenticeships(async_session, vault.id)

    await async_session.refresh(youth)
    assert result["stats_awarded"] == 1
    assert youth.strength == 3
    assert youth.apprentice_started_at > datetime.utcnow() - timedelta(seconds=5)


@pytest.mark.asyncio
async def test_apprenticeship_tick_supports_raw_sqlalchemy_async_session() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as raw_session:
        result = await game_loop_service._process_apprenticeships(raw_session, uuid4())

    await engine.dispose()
    assert result == {"active_count": 0, "stats_awarded": 0}


@pytest.mark.asyncio
async def test_apprentice_scenario_setup_creates_one_teen_and_is_idempotent(
    async_session: AsyncSession, vault: Vault
) -> None:
    room = await _create_production_room(async_session, vault)
    bottle_caps_before = vault.bottle_caps

    created = await apprentice_scenario_service.setup(async_session, vault.id)
    reused = await apprentice_scenario_service.setup(async_session, vault.id)

    dwellers = await crud.dweller.get_multi_by_vault(async_session, vault.id, age_group=AgeGroupEnum.TEEN)
    assert created.created is True
    assert reused.created is False
    assert created.apprentice.id == reused.apprentice.id
    assert created.apprentice.room_id == room.id
    assert created.apprentice.apprentice_stat == room.ability
    assert len(dwellers) == 1
    await async_session.refresh(vault)
    assert vault.bottle_caps == bottle_caps_before


@pytest.mark.asyncio
async def test_apprentice_scenario_ready_backdates_once_and_reports_status(
    async_session: AsyncSession, vault: Vault
) -> None:
    await _create_production_room(async_session, vault)

    result = await apprentice_scenario_service.setup(async_session, vault.id, ready=True)
    started_at = result.apprentice.apprentice_started_at
    assert started_at is not None
    status = await apprentice_scenario_service.get_status(async_session, vault.id)
    repeated = await apprentice_scenario_service.setup(async_session, vault.id, ready=True)

    assert result.ready is True
    assert status is not None
    assert status.ready is True
    assert datetime.utcnow() - started_at > timedelta(seconds=result.training_duration_seconds)
    assert repeated.apprentice.apprentice_started_at == started_at


@pytest.mark.asyncio
async def test_apprentice_scenario_requires_existing_production_room(async_session: AsyncSession, vault: Vault) -> None:
    with pytest.raises(ValueError, match="no production room"):
        await apprentice_scenario_service.setup(async_session, vault.id)


@pytest.mark.asyncio
async def test_adult_transition_clears_apprenticeship_state(async_session: AsyncSession, vault: Vault) -> None:
    youth = await _create_youth(async_session, vault, "Ada")
    room = await _create_production_room(async_session, vault)
    await crud.dweller.move_to_room(async_session, youth.id, room.id)
    youth.birth_date = datetime.utcnow() - timedelta(hours=10_000)
    await async_session.commit()

    await BreedingService.age_children(async_session, vault.id)

    await async_session.refresh(youth)
    assert youth.age_group == AgeGroupEnum.ADULT
    assert youth.apprentice_stat is None
    assert youth.apprentice_started_at is None
