"""PostgreSQL races, snapshot reads, and late-failure rollback for the Combat Zone."""

import asyncio

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.enums import (
    AgeGroupEnum,
    CombatZoneMatchStatus,
    CombatZonePartyStatus,
    DwellerStatusEnum,
    GenderEnum,
    NotificationType,
    RarityEnum,
)
from app.core.game_config import game_config
from app.crud import dweller as dweller_crud
from app.crud.combat_zone import combat_zone_crud
from app.models.combat_zone import CombatZoneParty
from app.models.dweller import Dweller
from app.models.notification import Notification
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services.combat.combat_zone_service import combat_zone_service
from app.services.notification_service import NotificationService
from app.tests.test_db.test_collectible_award_concurrency import vault_with_dweller
from app.utils.exceptions import DomainError

pytest_plugins = ["app.tests.test_alembic._support"]


@pytest.fixture(autouse=True)
def combat_zone_enabled(monkeypatch):
    monkeypatch.setattr(game_config.combat_zone, "enabled", True)
    monkeypatch.setattr(game_config.combat_zone, "travel_seconds", 0)
    monkeypatch.setattr("app.services.combat.combat_zone_service.request_combat_zone_tick", lambda: None)


async def _second_dweller(db: AsyncSession, vault_id, name: str) -> Dweller:
    return await dweller_crud.create(
        db_session=db,
        obj_in=DwellerCreate(
            vault_id=vault_id,
            first_name=name,
            last_name="Zone",
            gender=GenderEnum.MALE,
            age_group=AgeGroupEnum.ADULT,
            rarity=RarityEnum.COMMON,
            level=5,
            experience=0,
            max_health=100,
            health=100,
            radiation=0,
            happiness=50,
            strength=5,
            perception=5,
            endurance=5,
            charisma=5,
            intelligence=5,
            agility=5,
            luck=5,
        ),
    )


async def _queued_duel(maker: async_sessionmaker) -> tuple:
    async with maker() as db:
        _, vault_a, dweller_a = await vault_with_dweller(db, prefix="zone-race-a")
        vault_a_id, dweller_a_id = vault_a.id, dweller_a.id
        _, vault_b, dweller_b = await vault_with_dweller(db, prefix="zone-race-b")
        vault_b_id, dweller_b_id = vault_b.id, dweller_b.id
        party_a = await combat_zone_service.send_party(db, vault_a_id, dweller_a_id)
        party_b = await combat_zone_service.send_party(db, vault_b_id, dweller_b_id)
        await db.execute(
            update(CombatZoneParty)
            .where(CombatZoneParty.id.in_([party_a.id, party_b.id]))
            .values(status=CombatZonePartyStatus.QUEUED)
        )
        await db.commit()
        dweller_b.health = 1
        db.add(dweller_b)
        await db.commit()
        match = await combat_zone_service.challenge(db, vault_a_id, party_b.id)
        return vault_a_id, vault_b_id, dweller_a_id, dweller_b_id, match.id


async def _snapshot(maker: async_sessionmaker, ids: tuple) -> dict:
    vault_a_id, vault_b_id, dweller_a_id, dweller_b_id, match_id = ids
    async with maker() as db:
        match = await combat_zone_crud.get_match(db, match_id)
        party_a = await combat_zone_crud.get_party_by_vault(db, vault_a_id)
        party_b = await combat_zone_crud.get_party_by_vault(db, vault_b_id)
        vault_a = await db.get(Vault, vault_a_id)
        vault_b = await db.get(Vault, vault_b_id)
        dweller_a = await dweller_crud.get(db, dweller_a_id)
        dweller_b = await dweller_crud.get(db, dweller_b_id)
        events = await combat_zone_crud.list_events(db, match_id)
        notifications = await db.execute(
            select(func.count(Notification.id)).where(Notification.vault_id.in_([vault_a_id, vault_b_id]))
        )
        assert match is not None
        assert party_a is not None
        assert party_b is not None
        assert vault_a is not None
        assert vault_b is not None
        assert dweller_a is not None
        assert dweller_b is not None
        return {
            "status": match.status,
            "round": match.round_seq,
            "next": match.next_attack_party,
            "carry": match.carry,
            "a_health": match.party_a_health,
            "b_health": match.party_b_health,
            "a_credited": match.party_a_credited_caps,
            "b_credited": match.party_b_credited_caps,
            "a_status": party_a.status,
            "b_status": party_b.status,
            "a_escrow": party_a.escrow_caps,
            "b_escrow": party_b.escrow_caps,
            "a_caps": vault_a.bottle_caps,
            "b_caps": vault_b.bottle_caps,
            "a_dweller_health": dweller_a.health,
            "b_dweller_health": dweller_b.health,
            "events": len(events),
            "notifications": notifications.scalar_one(),
        }


@pytest.mark.integration
async def test_concurrent_first_sends_allow_one_party(live_pg_engine: AsyncEngine) -> None:
    maker = async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as db:
        _, vault, first = await vault_with_dweller(db, prefix="zone-send")
        second = await _second_dweller(db, vault.id, "Second")
        vault.bottle_caps = 1_000
        db.add(vault)
        await db.commit()
        vault_id, first_id, second_id = vault.id, first.id, second.id

    async def _send(dweller_id) -> object:
        async with maker() as session:
            try:
                return await combat_zone_service.send_party(session, vault_id, dweller_id)
            except DomainError as exc:
                return exc

    results = await asyncio.gather(_send(first_id), _send(second_id))
    assert sum(not isinstance(result, DomainError) for result in results) == 1

    async with maker() as db:
        parties = (
            (await db.execute(select(CombatZoneParty).where(CombatZoneParty.vault_id == vault_id))).scalars().all()
        )
        stored_vault = await db.get(Vault, vault_id)
        dwellers = (await db.execute(select(Dweller).where(Dweller.vault_id == vault_id))).scalars().all()

    assert len(parties) == 1
    assert stored_vault is not None
    assert stored_vault.bottle_caps == 900
    assert sum(dweller.status == DwellerStatusEnum.FIGHTING for dweller in dwellers) == 1


@pytest.mark.integration
async def test_send_and_recall_do_not_deadlock(live_pg_engine: AsyncEngine) -> None:
    maker = async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as db:
        _, vault, first = await vault_with_dweller(db, prefix="zone-recall")
        second = await _second_dweller(db, vault.id, "Second")
        vault.bottle_caps = 1_000
        db.add(vault)
        await db.commit()
        vault_id, first_id, second_id = vault.id, first.id, second.id
        party = await combat_zone_service.send_party(db, vault_id, first_id)
        await db.execute(
            update(CombatZoneParty).where(CombatZoneParty.id == party.id).values(status=CombatZonePartyStatus.QUEUED)
        )
        await db.commit()

    async def _send() -> object:
        async with maker() as session:
            try:
                return await combat_zone_service.send_party(session, vault_id, second_id)
            except DomainError as exc:
                return exc

    async def _recall() -> object:
        async with maker() as session:
            return await combat_zone_service.recall_party(session, vault_id)

    results = await asyncio.wait_for(asyncio.gather(_send(), _recall(), return_exceptions=True), timeout=5)
    assert not any(isinstance(result, asyncio.TimeoutError) for result in results)
    assert sum(isinstance(result, DomainError) for result in results) == 1

    async with maker() as db:
        stored = await combat_zone_crud.get_party_by_vault(db, vault_id)
        stored_vault = await db.get(Vault, vault_id)
    assert stored is not None
    assert stored.status == CombatZonePartyStatus.RETURNING
    assert stored_vault is not None
    assert stored_vault.bottle_caps == 1_000


@pytest.mark.integration
async def test_concurrent_ticks_settle_once(live_pg_engine: AsyncEngine) -> None:
    maker = async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)
    vault_a_id, vault_b_id, _dweller_a_id, _dweller_b_id, match_id = await _queued_duel(maker)

    async def _tick():
        async with maker() as session:
            return await combat_zone_service.process_ticks(session, seconds_passed=2)

    await asyncio.gather(_tick(), _tick())

    async with maker() as db:
        match = await combat_zone_crud.get_match(db, match_id)
        assert match is not None
        assert match.status == CombatZoneMatchStatus.FINISHED
        count = await db.execute(
            select(func.count(Notification.id)).where(
                Notification.vault_id.in_([vault_a_id, vault_b_id]),
                Notification.notification_type.in_([NotificationType.COMBAT_VICTORY, NotificationType.COMBAT_DEFEAT]),
            )
        )
        assert count.scalar_one() == 2


@pytest.mark.integration
@pytest.mark.parametrize("reader", ["detail", "events"])
async def test_match_reads_use_one_snapshot(live_pg_engine: AsyncEngine, monkeypatch, reader: str) -> None:
    maker = async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)
    ids = await _queued_duel(maker)
    vault_a_id, _vault_b_id, _dweller_a_id, _dweller_b_id, match_id = ids
    before = await _snapshot(maker, ids)
    async with maker() as db:
        vault_a = await db.get(Vault, vault_a_id)
        assert vault_a is not None
        assert vault_a.user_id is not None
        user_a_id = vault_a.user_id

    original = combat_zone_crud.list_events
    paused = asyncio.Event()
    resume = asyncio.Event()

    async def wrapped(db_session, match_id_arg, after_sequence=None):
        paused.set()
        await resume.wait()
        return await original(db_session, match_id_arg, after_sequence)

    monkeypatch.setattr(combat_zone_crud, "list_events", wrapped)

    async def _tick() -> None:
        await paused.wait()
        try:
            async with maker() as session:
                await combat_zone_service.process_ticks(session, seconds_passed=2)
        finally:
            resume.set()

    task = asyncio.create_task(_tick())
    async with maker() as session:
        if reader == "detail":
            view = await combat_zone_service.get_match(session, match_id, viewer_user_id=user_a_id)
            assert view.status == "active"
            assert view.cursor.status == "active"
            assert view.party_b.fighter.health == before["b_dweller_health"]
            assert len(view.events) == before["events"]
            assert all(event.kind != "finish" for event in view.events)
        else:
            events = await combat_zone_service.get_events(session, match_id, viewer_user_id=user_a_id)
            assert len(events) == before["events"]
            assert all(event.kind != "finish" for event in events)
    await asyncio.wait_for(task, timeout=5)

    async with maker() as session:
        finished = await combat_zone_service.get_match(session, match_id, viewer_user_id=user_a_id)
    assert finished.status == "finished"
    assert finished.cursor.status == "finished"


@pytest.mark.integration
async def test_payout_failure_rolls_back_balances_escrow_and_journal(live_pg_engine: AsyncEngine, monkeypatch) -> None:
    maker = async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)
    ids = await _queued_duel(maker)
    before = await _snapshot(maker, ids)
    delivered: list[object] = []

    async def fake_deliver(*args, **kwargs) -> None:
        delivered.append((args, kwargs))

    monkeypatch.setattr(NotificationService, "_deliver", fake_deliver)

    async with maker() as db:
        await db.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION combat_zone_fail_payout() RETURNS trigger AS $$
                BEGIN
                    IF NEW.bottle_caps IS DISTINCT FROM OLD.bottle_caps THEN
                        RAISE EXCEPTION 'simulated combat zone payout failure';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        await db.execute(
            text(
                "CREATE TRIGGER combat_zone_fail_payout BEFORE UPDATE ON vault "
                "FOR EACH ROW EXECUTE FUNCTION combat_zone_fail_payout()"
            )
        )
        await db.commit()

    try:
        with pytest.raises(SQLAlchemyError):
            async with maker() as session:
                await combat_zone_service.process_ticks(session, seconds_passed=2)
    finally:
        async with maker() as db:
            await db.execute(text("DROP TRIGGER IF EXISTS combat_zone_fail_payout ON vault"))
            await db.execute(text("DROP FUNCTION IF EXISTS combat_zone_fail_payout()"))
            await db.commit()

    assert await _snapshot(maker, ids) == before
    assert delivered == []


@pytest.mark.integration
async def test_rollback_after_the_first_notification_is_staged(live_pg_engine: AsyncEngine, monkeypatch) -> None:
    maker = async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)
    ids = await _queued_duel(maker)
    before = await _snapshot(maker, ids)
    delivered: list[object] = []
    queued_lengths: list[int] = []

    async def fake_deliver(*args, **kwargs) -> None:
        delivered.append((args, kwargs))

    original_create = NotificationService.create_and_send

    async def spy_create(db_session, *args, **kwargs):
        result = await original_create(db_session, *args, **kwargs)
        queued_lengths.append(len(db_session.info.get("deferred_notification_deliveries", [])))
        return result

    monkeypatch.setattr(NotificationService, "_deliver", fake_deliver)
    monkeypatch.setattr(NotificationService, "create_and_send", spy_create)

    async with maker() as db:
        await db.execute(text("CREATE SEQUENCE combat_zone_notification_fail_seq"))
        await db.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION combat_zone_fail_notification() RETURNS trigger AS $$
                BEGIN
                    IF nextval('combat_zone_notification_fail_seq') >= 2 THEN
                        RAISE EXCEPTION 'simulated second notification staging failure';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        await db.execute(
            text(
                "CREATE TRIGGER combat_zone_fail_notification BEFORE INSERT ON notification "
                "FOR EACH ROW EXECUTE FUNCTION combat_zone_fail_notification()"
            )
        )
        await db.commit()

    try:
        with pytest.raises(SQLAlchemyError):
            async with maker() as session:
                await combat_zone_service.process_ticks(session, seconds_passed=2)
    finally:
        async with maker() as db:
            await db.execute(text("DROP TRIGGER IF EXISTS combat_zone_fail_notification ON notification"))
            await db.execute(text("DROP FUNCTION IF EXISTS combat_zone_fail_notification()"))
            await db.execute(text("DROP SEQUENCE IF EXISTS combat_zone_notification_fail_seq"))
            await db.commit()

    assert queued_lengths
    assert queued_lengths[0] == 1
    assert await _snapshot(maker, ids) == before
    assert delivered == []
