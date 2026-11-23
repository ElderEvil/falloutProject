from datetime import timedelta

import pytest
import pytest_asyncio
from sqlalchemy import event

from app import crud
from app.core.enums import DeathCauseEnum, DwellerStatusEnum, LifecycleEnum
from app.crud.user_profile import profile_crud
from app.schemas.dweller import DwellerCreate
from app.schemas.user import UserCreate
from app.services.family.death_service import death_service
from app.tests.factory.dwellers import create_fake_dweller
from app.utils.exceptions import AccessDeniedException, ContentNoChangeException, InsufficientResourcesException
from app.utils.time import utcnow

pytestmark = pytest.mark.asyncio


async def _dweller(session, vault, first_name="Alive", **over):
    data = (
        create_fake_dweller()
        | {
            "first_name": first_name,
            "last_name": "Dweller",
            "health": 100,
            "max_health": 100,
            "level": 5,
        }
        | over
    )
    return await crud.dweller.create(session, obj_in=DwellerCreate(**data, vault_id=vault.id))


_DEAD = {
    "status": DwellerStatusEnum.DEAD.value,
    "is_dead": True,
    "is_permanently_dead": False,
    "death_timestamp": utcnow() - timedelta(days=2),
    "death_cause": DeathCauseEnum.HEALTH.value,
    "epitaph": "Test epitaph",
    "health": 0,
}


async def _owner_with_caps(session, vault, caps=10000):
    vault.bottle_caps = caps
    session.add(vault)
    await session.commit()
    return await crud.user.get(session, vault.user_id)


@pytest_asyncio.fixture(name="alive_dweller")
async def _alive_dweller(async_session, vault):
    return await _dweller(async_session, vault, "Alive", status=DwellerStatusEnum.IDLE.value, is_dead=False)


@pytest_asyncio.fixture(name="dead_dweller")
async def _dead_dweller(async_session, vault):
    return await _dweller(async_session, vault, "Dead", **_DEAD)


@pytest_asyncio.fixture(name="permanently_dead_dweller")
async def _permanently_dead_dweller(async_session, vault):
    return await _dweller(
        async_session,
        vault,
        "Permanent",
        **_DEAD
        | {
            "last_name": "Dead",
            "is_permanently_dead": True,
            "death_timestamp": utcnow() - timedelta(days=10),
            "death_cause": DeathCauseEnum.COMBAT.value,
            "epitaph": "Gone forever",
            "level": 10,
        },
    )


async def test_mark_as_dead_already_dead_raises(async_session, dead_dweller):
    with pytest.raises(ContentNoChangeException):
        await death_service.mark_as_dead(async_session, dead_dweller, DeathCauseEnum.HEALTH)


async def test_mark_as_dead_records_bio_and_clears_happiness(async_session, alive_dweller):
    updated = await death_service.mark_as_dead(async_session, alive_dweller, DeathCauseEnum.COMBAT)

    assert updated.status == DwellerStatusEnum.DEAD
    assert updated.is_dead is True
    assert updated.happiness == 0
    death_entry = next(entry for entry in updated.bio_entries if entry["source"] == "family")
    assert "died" in death_entry["text"].lower()
    assert death_entry["ref"] == {"cause": DeathCauseEnum.COMBAT.value}


async def test_mark_as_dead_rolls_back_when_stat_write_fails(async_session, db_connection, alive_dweller):
    # A failed counter write must not leave a durable death behind.

    def fail_profile_write(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("UPDATE userprofile "):
            raise RuntimeError("stat write failed")

    dweller_id = alive_dweller.id
    event.listen(db_connection.sync_connection, "before_cursor_execute", fail_profile_write)
    try:
        with pytest.raises(RuntimeError, match="stat write failed"):
            await death_service.mark_as_dead(async_session, alive_dweller, DeathCauseEnum.COMBAT)
    finally:
        event.remove(db_connection.sync_connection, "before_cursor_execute", fail_profile_write)

    reloaded = await crud.dweller.get(async_session, dweller_id)
    assert reloaded.is_dead is False
    assert reloaded.status != DwellerStatusEnum.DEAD
    assert not async_session.info.get("deferred_notification_deliveries")


async def test_revive_dweller_success(async_session, vault, dead_dweller):
    owner = await _owner_with_caps(async_session, vault)
    result = await death_service.revive_dweller(async_session, dead_dweller.id, owner)

    assert result.dweller.is_dead is False
    assert result.dweller.status == DwellerStatusEnum.IDLE
    assert result.dweller.death_timestamp is None
    assert result.dweller.death_cause is None
    assert result.dweller.health > 0
    assert result.caps_spent == death_service.get_revival_cost(dead_dweller.level)
    assert result.remaining_caps == 10000 - result.caps_spent


async def test_revive_locks_the_vault_before_deducting_caps(async_session, db_connection, vault, dead_dweller):
    # SQLite makes FOR UPDATE a no-op and cannot interleave two transactions, so the race itself is not
    # reproducible here; instead observe the ORM statements: the locking vault SELECT must precede the caps UPDATE.
    owner = await _owner_with_caps(async_session, vault)
    statements: list[tuple[str, bool]] = []

    def record(_connection, _cursor, statement, _parameters, context, _executemany):
        original = getattr(getattr(context, "compiled", None), "statement", None)
        locked = getattr(original, "_for_update_arg", None) is not None
        statements.append((statement, locked))

    event.listen(db_connection.sync_connection, "before_cursor_execute", record)
    try:
        result = await death_service.revive_dweller(async_session, dead_dweller.id, owner)
    finally:
        event.remove(db_connection.sync_connection, "before_cursor_execute", record)

    locked_vault_reads = [i for i, (sql, locked) in enumerate(statements) if locked and sql.startswith("SELECT vault.")]
    vault_updates = [i for i, (sql, _) in enumerate(statements) if sql.startswith("UPDATE vault ")]
    assert locked_vault_reads, "revival must read the vault row FOR UPDATE"
    assert vault_updates, "revival must write the deducted balance"
    assert locked_vault_reads[0] < vault_updates[0], "the locked read must precede the caps write"
    await async_session.refresh(vault)
    assert vault.bottle_caps == 10000 - result.caps_spent


async def test_revive_duplicate_request_deducts_caps_only_once(async_session, vault, dead_dweller):
    owner = await _owner_with_caps(async_session, vault)
    result = await death_service.revive_dweller(async_session, dead_dweller.id, owner)
    with pytest.raises(ContentNoChangeException):
        await death_service.revive_dweller(async_session, dead_dweller.id, owner)

    await async_session.refresh(vault)
    await async_session.refresh(dead_dweller)
    assert vault.bottle_caps == 10000 - result.caps_spent
    assert dead_dweller.is_dead is False


async def test_revive_distinct_dwellers_deducts_each_cost(async_session, vault, dead_dweller):
    owner = await _owner_with_caps(async_session, vault)
    other_dweller = await _dweller(async_session, vault, "Other", **_DEAD | {"last_name": "Dead"})

    first = await death_service.revive_dweller(async_session, dead_dweller.id, owner)
    second = await death_service.revive_dweller(async_session, other_dweller.id, owner)

    await async_session.refresh(vault)
    assert vault.bottle_caps == 10000 - first.caps_spent - second.caps_spent
    assert first.remaining_caps == 10000 - first.caps_spent
    assert second.remaining_caps == 10000 - first.caps_spent - second.caps_spent


async def test_revive_clears_radiation(async_session, vault, dead_dweller):
    vault.bottle_caps = 10000
    async_session.add(vault)
    await crud.dweller.update(async_session, dead_dweller.id, {"radiation": 40})
    await async_session.commit()
    owner = await crud.user.get(async_session, vault.user_id)

    result = await death_service.revive_dweller(async_session, dead_dweller.id, owner)

    assert result.dweller.radiation == 0


@pytest.mark.parametrize("operation", ["revive_dweller", "build_revival_quote"])
async def test_revival_rejects_foreign_vault_owner(async_session, vault, dead_dweller, operation):
    await _owner_with_caps(async_session, vault)
    intruder = await crud.user.create(
        db_session=async_session,
        obj_in=UserCreate(username="intruder", email="intruder@example.com", password="testpass123"),
    )

    with pytest.raises(AccessDeniedException):
        await getattr(death_service, operation)(async_session, dead_dweller.id, intruder)

    await async_session.refresh(dead_dweller)
    await async_session.refresh(vault)
    assert dead_dweller.is_dead is True
    assert vault.bottle_caps == 10000


async def test_build_revival_quote_matches_cost_and_affordability(async_session, vault, dead_dweller):
    # The quote reuses the single cost path and reports affordability.
    vault.bottle_caps = dead_dweller.level * 10
    async_session.add(vault)
    await async_session.commit()
    owner = await crud.user.get(async_session, vault.user_id)

    quote = await death_service.build_revival_quote(async_session, dead_dweller.id, owner)

    assert quote.revival_cost == death_service.get_revival_cost(dead_dweller.level)
    assert quote.vault_caps == vault.bottle_caps
    assert quote.can_afford == (vault.bottle_caps >= quote.revival_cost)


async def test_revival_rejects_living_dweller(async_session, vault, alive_dweller):
    owner = await _owner_with_caps(async_session, vault)
    with pytest.raises(ContentNoChangeException):
        await death_service.build_revival_quote(async_session, alive_dweller.id, owner)
    with pytest.raises(ContentNoChangeException) as exc_info:
        await death_service.revive_dweller(async_session, alive_dweller.id, owner)
    assert "not dead" in str(exc_info.value.detail).lower()


async def test_revive_dweller_insufficient_caps(async_session, vault, dead_dweller):
    owner = await _owner_with_caps(async_session, vault, caps=10)
    with pytest.raises(InsufficientResourcesException):
        await death_service.revive_dweller(async_session, dead_dweller.id, owner)


async def test_revive_permanently_dead_raises(async_session, vault, permanently_dead_dweller):
    owner = await _owner_with_caps(async_session, vault)
    with pytest.raises(ContentNoChangeException) as exc_info:
        await death_service.revive_dweller(async_session, permanently_dead_dweller.id, owner)
    assert "permanently dead" in str(exc_info.value.detail).lower()


@pytest.mark.parametrize(("level", "cost"), [(6, 450), (10, 750), (11, 1100), (20, 2000), (50, 2000)])
async def test_get_revival_cost_tiers(level, cost):
    assert death_service.get_revival_cost(level) == cost


async def test_get_days_until_permanent_alive_dweller(alive_dweller):
    assert death_service.get_days_until_permanent(alive_dweller) is None


async def test_get_days_until_permanent_recently_dead(async_session, vault):
    dweller = await _dweller(async_session, vault, "Recent", **_DEAD | {"last_name": "Death"})
    days_left = death_service.get_days_until_permanent(dweller)
    assert days_left is not None
    assert 4 <= days_left <= 5


async def test_check_and_mark_permanent_deaths(async_session, vault):
    expired = await _dweller(
        async_session,
        vault,
        "Expired",
        **_DEAD
        | {
            "last_name": "Death",
            "death_timestamp": utcnow() - timedelta(days=10),
            "death_cause": DeathCauseEnum.EXPLORATION.value,
        },
    )
    recent = await _dweller(
        async_session,
        vault,
        "Recent",
        **_DEAD
        | {
            "last_name": "Death",
            "death_timestamp": utcnow() - timedelta(days=2),
            "death_cause": DeathCauseEnum.INCIDENT.value,
        },
    )
    await async_session.commit()

    count = await death_service.check_and_mark_permanent_deaths(async_session)
    await async_session.commit()

    assert count == 1
    await async_session.refresh(expired)
    await async_session.refresh(recent)
    assert expired.is_permanently_dead is True
    assert recent.is_permanently_dead is False


async def test_get_death_statistics(async_session, vault, dead_dweller, permanently_dead_dweller):
    if not await profile_crud.get_by_user_id(async_session, vault.user_id):
        await profile_crud.create_for_user(async_session, vault.user_id)

    stats = await death_service.get_death_statistics(async_session, vault.user_id)

    for key in (
        "total_dwellers_born",
        "total_dwellers_died",
        "deaths_by_cause",
        "revivable_count",
        "permanently_dead_count",
    ):
        assert key in stats
    assert stats["revivable_count"] == 1
    assert stats["permanently_dead_count"] == 1


@pytest.mark.parametrize("method", ["get_dead_dwellers", "get_graveyard"])
async def test_dead_dweller_queries(
    async_session, vault, dead_dweller, permanently_dead_dweller, alive_dweller, method
):
    expected = dead_dweller if method == "get_dead_dwellers" else permanently_dead_dweller
    result = await getattr(crud.dweller, method)(async_session, vault.id)

    assert len(result) == 1
    assert result[0].id == expected.id
    if method == "get_graveyard":
        assert result[0].is_permanently_dead is True


@pytest.mark.parametrize("operation", ["build_revival_quote", "revive_dweller"])
@pytest.mark.parametrize(
    ("lifecycle", "dead", "permanent", "eligible"),
    [
        ("dead_permanent", False, False, False),
        ("alive", True, True, False),
        ("dead_revivable", False, True, True),
        (None, True, True, False),
        (None, False, False, False),
        (None, True, False, True),
    ],
)
async def test_revival_uses_canonical_eligibility(
    async_session, vault, dead_dweller, operation, lifecycle, dead, permanent, eligible
):
    owner = await _owner_with_caps(async_session, vault)
    dead_dweller.lifecycle = LifecycleEnum(lifecycle) if lifecycle else None
    dead_dweller.is_dead = dead
    dead_dweller.is_permanently_dead = permanent
    dead_dweller.death_timestamp = None
    await async_session.commit()
    memorial = (dead_dweller.epitaph, dead_dweller.lifecycle, dead_dweller.health)
    action = getattr(death_service, operation)
    if eligible:
        result = await action(async_session, dead_dweller.id, owner)
        if operation == "build_revival_quote":
            assert result.days_until_permanent is None
            assert result.can_afford
        else:
            await async_session.refresh(dead_dweller)
            assert dead_dweller.lifecycle == LifecycleEnum.ALIVE
    else:
        with pytest.raises(ContentNoChangeException):
            await action(async_session, dead_dweller.id, owner)
        await async_session.refresh(vault)
        await async_session.refresh(dead_dweller)
        assert vault.bottle_caps == 10000
        assert (dead_dweller.epitaph, dead_dweller.lifecycle, dead_dweller.health) == memorial
