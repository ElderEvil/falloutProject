"""Vault creation owns one transaction boundary (real session).

SERVICE_LAYER.md "Transaction ownership": ``VaultService.initiate_vault`` commits once and
every callee stages its rows with ``commit=False``. These tests pin the observable contract
on the test database: one durable vault + slot + storage + rooms + dwellers + game state +
objectives on success, nothing surviving a failure at a later write, and an admin endpoint
that produces exactly what the service path produces.
"""

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from sqlalchemy import event, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.event_bus import GameEvent, event_bus
from app.models import Dweller, Junk, Outfit, Room, Storage, Training, Weapon
from app.models.game_state import GameState
from app.models.objective import Objective
from app.models.vault import Vault
from app.models.vault_objective import VaultObjectiveProgressLink
from app.models.vault_slot import VaultSlot
from app.schemas.vault import VaultCreate, VaultNumber
from app.services.notification_service import NotificationService
from app.services.vault_service import vault_service
from app.tests.factory.vaults import create_fake_vault, random_vault_number
from app.utils.seed_objectives import seed_objectives_from_json

pytestmark = pytest.mark.asyncio

FaultHook = Callable[[str], object]
COMPARED_VAULT_FIELDS = (
    "user_id",
    "bottle_caps",
    "happiness",
    "power",
    "food",
    "water",
    "population_max",
    "vault_mode",
    "scenario_key",
    "is_deleted",
)


@asynccontextmanager
async def _fail_sql(async_session: AsyncSession, predicate: FaultHook, message: str) -> AsyncGenerator[None]:
    """Raise at the first statement matching ``predicate`` while the block runs."""
    connection = (await async_session.connection()).sync_connection

    def hook(_conn, _cursor, statement, _parameters, _context, _many) -> None:
        if predicate(statement):
            raise RuntimeError(message)

    event.listen(connection, "before_cursor_execute", hook)
    try:
        yield
    finally:
        event.remove(connection, "before_cursor_execute", hook)


def _inserts_room(statement: str) -> bool:
    """The first room insert is the third write of the operation (vault, slot, room)."""
    return statement.lower().startswith("insert into room")


def _inserts_initial_item(statement: str) -> bool:
    """Boosted junk is the last initial-item write, long after objectives and training are staged."""
    return statement.lower().startswith("insert into junk")


async def _count(session: AsyncSession, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


def _counting_commit(session: AsyncSession) -> list[int]:
    commits: list[int] = []
    original_commit = session.commit

    async def counting_commit() -> None:
        commits.append(1)
        await original_commit()

    session.commit = counting_commit  # type: ignore[method-assign]
    return commits


async def test_initiate_vault_commits_once_and_persists_the_whole_vault(async_session, superuser) -> None:
    await seed_objectives_from_json(async_session)
    commits = _counting_commit(async_session)

    vault = await vault_service.initiate_vault(async_session, VaultNumber(number=random_vault_number()), superuser.id)

    assert len(commits) == 1, f"vault creation committed {len(commits)} times; the service owns exactly one"
    vaults = (await async_session.execute(select(Vault).where(Vault.number == vault.number))).scalars().all()
    assert len(vaults) == 1, "a fresh vault number must produce exactly one vault row"
    assert vaults[0].id == vault.id
    assert await _count(async_session, VaultSlot) == 1
    assert await _count(async_session, Storage) == 1
    assert await _count(async_session, Room) > 0
    assert await _count(async_session, Dweller) > 0
    assert await _count(async_session, GameState) == 1, "the vault's game state must exist exactly once"
    game_state = await async_session.execute(select(GameState).where(GameState.vault_id == vault.id))
    assert game_state.scalar_one().achievement_tracks_initialized
    links = await async_session.execute(
        select(func.count())
        .select_from(VaultObjectiveProgressLink)
        .where(VaultObjectiveProgressLink.vault_id == vault.id)
    )
    assert int(links.scalar_one()) > 0, "starter objectives must be linked to the vault"


async def test_failure_at_a_later_write_leaves_no_vault_and_no_orphaned_game_state(async_session, superuser) -> None:
    await seed_objectives_from_json(async_session)

    with pytest.raises(RuntimeError, match="injected room write failure"):
        async with _fail_sql(async_session, _inserts_room, "injected room write failure"):
            await vault_service.initiate_vault(async_session, VaultNumber(number=random_vault_number()), superuser.id)
    await async_session.rollback()

    assert await _count(async_session, Vault) == 0, "a failed vault creation must not leave a vault row"
    assert await _count(async_session, VaultSlot) == 0, "a failed vault creation must not keep its atlas slot"
    assert await _count(async_session, GameState) == 0, "a failed vault creation must not leave orphaned game state"
    assert await _count(async_session, Storage) == 0
    assert await _count(async_session, Room) == 0
    assert await _count(async_session, Dweller) == 0


async def test_endpoint_and_service_paths_produce_identical_vaults(
    async_session, superuser, async_client, superuser_token_headers
) -> None:
    """The admin endpoint delegates to the service instead of writing through CRUD itself."""
    payload = create_fake_vault()
    endpoint_payload = {**payload, "user_id": str(superuser.id)}
    response = await async_client.post("/vaults/", headers=superuser_token_headers, json=endpoint_payload)
    assert response.status_code == 201
    endpoint_vault = (
        await async_session.execute(select(Vault).where(Vault.number == endpoint_payload["number"]))
    ).scalar_one()

    service_payload = VaultCreate(**{**payload, "number": random_vault_number()})
    if service_payload.number == payload["number"]:
        service_payload.number = random_vault_number()
    commits = _counting_commit(async_session)
    service_vault = await vault_service.create_vault(
        db_session=async_session, obj_in=service_payload, user_id=superuser.id
    )
    assert len(commits) == 1, f"the service path committed {len(commits)} times; it owns exactly one"

    body = response.json()
    assert body["number"] == endpoint_payload["number"]

    def _normalized(value):
        value = getattr(value, "value", value)
        return str(value) if isinstance(value, UUID) else value

    for field in COMPARED_VAULT_FIELDS:
        persisted = _normalized(getattr(endpoint_vault, field))
        assert persisted == _normalized(getattr(service_vault, field)), f"endpoint and service disagree on {field}"
        if field in body:
            assert body[field] == persisted, f"the endpoint response disagrees with its own row on {field}"
    assert endpoint_vault.id != service_vault.id
    assert await _count(async_session, VaultSlot) == 2, "both paths claim one atlas slot each"


@pytest.fixture
async def completion_notices() -> AsyncGenerator[list[dict]]:
    """Capture OBJECTIVE_COMPLETED payloads emitted during a test."""
    notices: list[dict] = []

    async def handler(_event_type: str, _vault_id: UUID, data: dict) -> None:
        notices.append(data)

    event_bus.subscribe(GameEvent.OBJECTIVE_COMPLETED, handler)
    try:
        yield notices
    finally:
        event_bus.unsubscribe(GameEvent.OBJECTIVE_COMPLETED, handler)


def _notices_seen_at_commit(session: AsyncSession, notices: list[dict]) -> list[int]:
    """Record how many notices already exist each time the session commits."""
    seen: list[int] = []
    original_commit = session.commit

    async def commit() -> None:
        seen.append(len(notices))
        await original_commit()

    session.commit = commit  # type: ignore[method-assign]
    return seen


async def test_boosted_creation_delivers_the_completion_it_earns(
    async_session, superuser, completion_notices: list[dict]
) -> None:
    """A boosted vault completes "Reach 10 Dwellers" while seeding; that notice must survive the commit."""
    await seed_objectives_from_json(async_session)
    notifications_before_commit = _notices_seen_at_commit(async_session, completion_notices)

    vault = await vault_service.initiate_vault(
        async_session, VaultNumber(number=random_vault_number()), superuser.id, is_boosted=True
    )

    assert notifications_before_commit == [0], "completion notices must not be emitted before the owning commit"
    challenges = [notice["challenge"] for notice in completion_notices]
    assert challenges == ["Reach 10 Dwellers"], (
        f"boosted creation delivered {challenges!r}; the completion earned during seeding was not drained after commit"
    )
    result = await async_session.execute(
        select(VaultObjectiveProgressLink).where(VaultObjectiveProgressLink.vault_id == vault.id)
    )
    completed = [link for link in result.scalars().all() if link.progress >= link.total]
    assert [link.objective_id for link in completed] == [UUID(completion_notices[0]["objective_id"])]
    assert "deferred_objective_completions" not in async_session.info


async def test_rolled_back_boosted_creation_parks_no_completions(
    async_session, superuser, completion_notices: list[dict]
) -> None:
    """A failure after the completion was queued must discard it along with the transaction."""
    await seed_objectives_from_json(async_session)

    with pytest.raises(RuntimeError, match="injected initial-item write failure"):
        async with _fail_sql(async_session, _inserts_initial_item, "injected initial-item write failure"):
            await vault_service.initiate_vault(
                async_session, VaultNumber(number=random_vault_number()), superuser.id, is_boosted=True
            )
    await async_session.rollback()

    assert completion_notices == [], "a rolled-back creation must not deliver objective completions"
    assert "deferred_objective_completions" not in async_session.info, (
        "a rolled-back creation left parked completions on the session"
    )
    assert await _count(async_session, Vault) == 0


async def test_non_boosted_creation_still_delivers_its_completions(
    async_session, superuser, completion_notices: list[dict]
) -> None:
    """The parked-queue drain must not cost the ordinary (non-boosted) creation its notices."""
    await seed_objectives_from_json(async_session)
    async_session.add(
        Objective(
            template_key="test:reach 1 dweller",
            challenge="Reach 1 Dweller",
            reward="10 caps",
            category="achievement",
            objective_type="reach",
            target_entity={"reach_type": "dweller_count"},
            target_amount=1,
            track_key="reach:dweller_count",
            sequence=0,
        )
    )
    await async_session.commit()

    vault = await vault_service.initiate_vault(
        async_session, VaultNumber(number=random_vault_number()), superuser.id, is_boosted=False
    )

    assert [notice["challenge"] for notice in completion_notices] == ["Reach 1 Dweller"]
    assert "deferred_objective_completions" not in async_session.info
    assert await _count(async_session, Vault) == 1


async def test_failure_after_objectives_and_training_rolls_back_the_boosted_seeding(
    async_session, superuser, monkeypatch, completion_notices: list[dict]
) -> None:
    """Inject the fault in ``seeding.create_initial_items`` (boosted junk insert).

    ``VaultService.initiate_vault`` assigns objectives (~line 151), seeds boosted themes and calls
    ``create_initial_items`` (~line 157). The junk flush inside ``seed_boosted_junk`` runs after the
    weapon/outfit flushes, so by the time the hook fires the objective links, the queued achievement
    completion and every training row have already been written in this transaction. A failure there
    must undo all of them and deliver nothing.
    """
    await seed_objectives_from_json(async_session)

    staged: list[str] = []
    connection = (await async_session.connection()).sync_connection

    def record(_conn, _cursor, statement, _parameters, _context, _many) -> None:
        tokens = statement.lower().split()
        prefix = tokens[2] if len(tokens) > 2 and tokens[:2] == ["insert", "into"] else ""
        if prefix in {"training", "vaultobjectiveprogresslink", "weapon", "junk", "outfit", "dweller"}:
            staged.append(prefix)

    delivered: list[dict] = []

    async def deliver(_user_id: UUID, payload: dict) -> None:
        delivered.append(payload)

    event.listen(connection, "before_cursor_execute", record)
    monkeypatch.setattr(NotificationService, "_deliver", staticmethod(deliver))
    try:
        with pytest.raises(RuntimeError, match="injected initial-item write failure"):
            async with _fail_sql(async_session, _inserts_initial_item, "injected initial-item write failure"):
                await vault_service.initiate_vault(
                    async_session, VaultNumber(number=random_vault_number()), superuser.id, is_boosted=True
                )
    finally:
        event.remove(connection, "before_cursor_execute", record)
    await async_session.rollback()

    assert {
        "training",
        "vaultobjectiveprogresslink",
        "junk",
    } <= set(staged), f"the fault fired before the intended stage was staged: {staged!r}"
    assert staged.index("training") < staged.index("junk"), "training rows must be staged before the junk fault"

    for model, label in (
        (Vault, "vault"),
        (VaultSlot, "atlas slot"),
        (Storage, "storage"),
        (Room, "room"),
        (Dweller, "dweller"),
        (Training, "training"),
        (VaultObjectiveProgressLink, "objective link"),
        (GameState, "game state"),
        (Weapon, "weapon"),
        (Outfit, "outfit"),
        (Junk, "junk"),
    ):
        assert await _count(async_session, model) == 0, f"a failed boosted creation left a {label} row"

    assert completion_notices == [], "a failed boosted creation delivered an objective completion"
    assert delivered == [], f"a failed boosted creation delivered notifications: {delivered!r}"
    assert "deferred_objective_completions" not in async_session.info
