"""Exit-request lifecycle: ask, refuse, withdraw, and the one-way grant."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import SPECIAL_STATS, AgeGroupEnum, DeathCauseEnum, DwellerStatusEnum, GenderEnum, RarityEnum
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services.exit_request_service import exit_request_service
from app.services.family.death_service import death_service
from app.utils.exceptions import ResourceNotFoundException, VaultOperationException


def _dweller_data(**overrides: object) -> dict:
    data: dict = {
        "first_name": "Nora",
        "last_name": "Kell",
        "gender": GenderEnum.FEMALE,
        "rarity": RarityEnum.COMMON,
        "age_group": AgeGroupEnum.ADULT,
        "is_adult": True,
        "birth_date": datetime.utcnow() - timedelta(days=365 * 30),
        "level": 5,
        "experience": 0,
        "max_health": 100,
        "health": 100,
        "radiation": 0,
        "happiness": 80,
        **dict.fromkeys(SPECIAL_STATS, 3),
    }
    data.update(overrides)
    return data


async def _create(db_session: AsyncSession, vault: Vault, **overrides: object) -> Dweller:
    return await crud.dweller.create(
        db_session=db_session, obj_in=DwellerCreate(**_dweller_data(**overrides), vault_id=vault.id)
    )


async def _populate(db_session: AsyncSession, vault: Vault, count: int) -> list[Dweller]:
    """The population floor needs more than `min_population` living dwellers."""
    return [await _create(db_session, vault, first_name=f"Dw{index}") for index in range(count)]


async def _with_room_for_one_exit(db_session: AsyncSession, vault: Vault) -> list[Dweller]:
    return await _populate(db_session, vault, game_config.exit_request.min_population + 1)


@pytest.mark.asyncio
async def test_request_exit_records_the_ask(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)

    result = await exit_request_service.request_exit(async_session, dwellers[0].id)

    assert result.exit_requested_at is not None
    assert [d.id for d in await exit_request_service.list_pending(async_session, vault.id)] == [dwellers[0].id]


@pytest.mark.asyncio
async def test_request_exit_is_refused_below_the_population_floor(async_session: AsyncSession, vault: Vault) -> None:
    """The vault cannot be emptied one despair at a time."""
    dwellers = await _populate(async_session, vault, game_config.exit_request.min_population)

    with pytest.raises(VaultOperationException, match="minimum population"):
        await exit_request_service.request_exit(async_session, dwellers[0].id)


@pytest.mark.asyncio
async def test_request_exit_rejects_children(async_session: AsyncSession, vault: Vault) -> None:
    await _with_room_for_one_exit(async_session, vault)
    child = await _create(async_session, vault, first_name="Pip", age_group=AgeGroupEnum.CHILD, is_adult=False)

    with pytest.raises(VaultOperationException, match="grown dwellers"):
        await exit_request_service.request_exit(async_session, child.id)


@pytest.mark.asyncio
async def test_request_exit_rejects_a_dweller_who_is_away(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)
    await crud.dweller.update(async_session, dwellers[0].id, {"status": DwellerStatusEnum.EXPLORING})

    with pytest.raises(VaultOperationException, match="away from the vault"):
        await exit_request_service.request_exit(async_session, dwellers[0].id)


@pytest.mark.asyncio
async def test_request_exit_unknown_dweller(async_session: AsyncSession, vault: Vault) -> None:
    with pytest.raises(ResourceNotFoundException):
        await exit_request_service.request_exit(async_session, uuid4())


@pytest.mark.asyncio
async def test_refuse_exit_costs_happiness_and_leaves_the_request_standing(
    async_session: AsyncSession, vault: Vault
) -> None:
    """A refusal must not silently cancel the ask — the dweller still wants to go."""
    dwellers = await _with_room_for_one_exit(async_session, vault)
    starting_happiness = dwellers[0].happiness
    await exit_request_service.request_exit(async_session, dwellers[0].id)

    refused = await exit_request_service.refuse_exit(async_session, vault, dwellers[0].id)

    assert refused.exit_requested_at is not None
    assert refused.happiness == starting_happiness - game_config.exit_request.refusal_happiness_penalty
    assert [d.id for d in await exit_request_service.list_pending(async_session, vault.id)] == [dwellers[0].id]


@pytest.mark.asyncio
async def test_refuse_exit_without_a_request_is_rejected(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)

    with pytest.raises(VaultOperationException, match="has not asked"):
        await exit_request_service.refuse_exit(async_session, vault, dwellers[0].id)


@pytest.mark.asyncio
async def test_grant_exit_is_permanent_death_by_exile(async_session: AsyncSession, vault: Vault) -> None:
    """The one-way ticket: dead by EXILE and past the revive window in the same write."""
    dwellers = await _with_room_for_one_exit(async_session, vault)
    await exit_request_service.request_exit(async_session, dwellers[0].id)

    granted = await exit_request_service.grant_exit(async_session, vault, dwellers[0].id)

    assert granted.is_dead is True
    assert granted.death_cause is DeathCauseEnum.EXILE
    assert granted.is_permanently_dead is True
    assert granted.status is DwellerStatusEnum.DEAD
    assert granted.exit_requested_at is None
    assert "did not return" in (granted.epitaph or "")
    assert granted.id not in [d.id for d in await exit_request_service.list_pending(async_session, vault.id)]


@pytest.mark.asyncio
async def test_granted_exit_has_no_revival_window(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)
    await exit_request_service.request_exit(async_session, dwellers[0].id)

    granted = await exit_request_service.grant_exit(async_session, vault, dwellers[0].id)

    assert death_service.get_days_until_permanent(granted) is None


@pytest.mark.asyncio
async def test_grant_exit_respects_the_population_floor(async_session: AsyncSession, vault: Vault) -> None:
    """A request raised when the vault was full is still held back once the vault is too small."""
    dwellers = await _with_room_for_one_exit(async_session, vault)
    await exit_request_service.request_exit(async_session, dwellers[0].id)
    for dweller in dwellers[1:]:
        await crud.dweller.update(async_session, dweller.id, {"is_dead": True, "health": 0})

    with pytest.raises(VaultOperationException, match="minimum population"):
        await exit_request_service.grant_exit(async_session, vault, dwellers[0].id)


@pytest.mark.asyncio
async def test_despair_makes_dwellers_ask(async_session: AsyncSession, vault: Vault) -> None:
    await _with_room_for_one_exit(async_session, vault)
    sad = await _create(async_session, vault, first_name="Clara", happiness=game_config.exit_request.despair_happiness)

    asked = await exit_request_service.sync_despair_requests(async_session, vault.id)

    assert [d.id for d in asked] == [sad.id]
    await async_session.refresh(sad)
    assert sad.exit_requested_at is not None


@pytest.mark.asyncio
async def test_recovery_withdraws_a_standing_request(async_session: AsyncSession, vault: Vault) -> None:
    """A dweller who feels better stops asking, without the player doing anything."""
    dwellers = await _with_room_for_one_exit(async_session, vault)
    sad = await _create(async_session, vault, first_name="Clara", happiness=game_config.exit_request.despair_happiness)
    await exit_request_service.request_exit(async_session, sad.id)

    await crud.dweller.update(async_session, sad.id, {"happiness": 90})
    await exit_request_service.sync_despair_requests(async_session, vault.id)

    await async_session.refresh(sad)
    assert sad.exit_requested_at is None
    assert all(d.exit_requested_at is None for d in dwellers)


@pytest.mark.asyncio
async def test_despair_leaves_content_dwellers_alone(async_session: AsyncSession, vault: Vault) -> None:
    dwellers = await _with_room_for_one_exit(async_session, vault)

    assert await exit_request_service.sync_despair_requests(async_session, vault.id) == []
    assert all(d.exit_requested_at is None for d in dwellers)
