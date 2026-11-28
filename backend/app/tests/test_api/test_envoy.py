"""Envoy Terminal: flag gating, the hail proximity gate, first contact and lockouts."""

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from math import hypot
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user
from app.core.enums import LocationTypeEnum, PlaceKindEnum
from app.core.game_config import game_config
from app.crud.vault_slot import vault_slot
from app.models.diplomatic_filing import DiplomaticFiling
from app.models.user import User
from app.models.world_location import VaultLocationState, WorldLocation
from app.utils.time import utcnow
from app.utils.vault_slots import slot_coords
from main import app


@pytest.fixture(autouse=True)
def _vault_diplomacy_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(game_config.features, "vault_diplomacy", True)


@pytest_asyncio.fixture(name="owner")
async def owner_fixture(user: User) -> AsyncGenerator[User]:
    app.dependency_overrides[get_current_active_user] = lambda: user
    try:
        yield user
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value)


async def _claim(async_session: AsyncSession, *vaults) -> list[int]:
    """Give each vault a slot on the shared atlas (reusing one a fixture already claimed)."""
    indices = []
    for vault in vaults:
        existing = await vault_slot.get_by_vault(async_session, vault.id)
        slot = (
            existing
            if existing is not None
            else await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
        )
        indices.append(slot.slot_index)
    return indices


async def _visit(async_session: AsyncSession, vault_id, coords: tuple[float, float]) -> None:
    """Record a visited place at ``coords`` for a vault, the way a dweller's trip would."""
    name = f"Relay {coords[0]}-{coords[1]}"
    place = WorldLocation(
        name=name, normalized_name=name.lower(), kind=PlaceKindEnum.PLACE, coord_x=coords[0], coord_y=coords[1]
    )
    async_session.add(place)
    await async_session.flush()
    async_session.add(VaultLocationState(vault_id=vault_id, location_id=place.id, type=LocationTypeEnum.VISITED))
    await async_session.commit()


async def _hail(client, vault, target):
    return await client.post(f"/vaults/{vault.id}/envoy/hail", json={"target_vault_id": str(target.id)})


def _signal(payload: list[dict], other) -> dict:
    return next(row for row in payload if row["vault_id"] == str(other.id))


async def test_flag_off_returns_404_on_all_six_routes(async_client, owner, vault, monkeypatch) -> None:
    monkeypatch.setattr(game_config.features, "vault_diplomacy", False)
    absent = "00000000-0000-0000-0000-000000000000"
    responses = [
        await async_client.get(f"/vaults/{vault.id}/envoy/signals"),
        await async_client.post(f"/vaults/{vault.id}/envoy/hail", json={"target_vault_id": absent}),
        await async_client.post(f"/vaults/{vault.id}/envoy/filings", json={"to_vault_id": absent}),
        await async_client.post(f"/vaults/{vault.id}/envoy/filings/{absent}/respond", json={"accept": True}),
        await async_client.get(f"/vaults/{vault.id}/envoy/log"),
        await async_client.get(f"/vaults/{vault.id}/envoy/config"),
    ]
    assert [response.status_code for response in responses] == [404] * 6


async def test_signals_gate_hailing_on_a_visited_place_in_range(
    async_client, owner, vault, user_with_vault, async_session
) -> None:
    _other_user, other = user_with_vault
    mine, theirs = await _claim(async_session, vault, other)

    far = await async_client.get(f"/vaults/{vault.id}/envoy/signals")
    assert far.status_code == 200, far.text
    signal = _signal(far.json(), other)
    assert signal["status"] == "UNMET"
    assert signal["can_hail"] is False
    assert signal["standing"] == 0
    assert signal["distance"] > game_config.diplomacy.hail_radius

    await _visit(async_session, vault.id, slot_coords(theirs))
    near = await async_client.get(f"/vaults/{vault.id}/envoy/signals")
    signal = _signal(near.json(), other)
    assert signal["can_hail"] is True
    mine_coords, their_coords = slot_coords(mine), slot_coords(theirs)
    assert signal["distance"] == round(hypot(their_coords[0] - mine_coords[0], their_coords[1] - mine_coords[1]), 1)


async def test_hail_files_one_pending_offer_that_reaches_the_targets_log(
    async_client, owner, vault, user_with_vault, async_session
) -> None:
    other_user, other = user_with_vault
    _mine, theirs = await _claim(async_session, vault, other)
    await _visit(async_session, vault.id, slot_coords(theirs))

    filed = await _hail(async_client, vault, other)
    assert filed.status_code == 201, filed.text
    body = filed.json()
    assert body["kind"] == "HAIL"
    assert body["status"] == "PENDING"
    assert body["incoming"] is False
    assert body["responded_at"] is None
    ttl = timedelta(hours=game_config.diplomacy.filing_ttl_hours)
    assert abs(_instant(body["expires_at"]) - _instant(body["created_at"]) - ttl) < timedelta(seconds=5)

    own_log = await async_client.get(f"/vaults/{vault.id}/envoy/log")
    assert [row["filing_id"] for row in own_log.json()] == [body["filing_id"]]
    assert own_log.json()[0]["incoming"] is False

    app.dependency_overrides[get_current_active_user] = lambda: other_user
    inbox = await async_client.get(f"/vaults/{other.id}/envoy/log")
    assert inbox.status_code == 200
    assert inbox.json()[0]["incoming"] is True
    signals = await async_client.get(f"/vaults/{other.id}/envoy/signals")
    assert _signal(signals.json(), vault)["incoming_hail"] is True


async def test_hail_rejects_out_of_range_self_and_duplicate(
    async_client, owner, vault, user_with_vault, async_session
) -> None:
    _other_user, other = user_with_vault
    _mine, theirs = await _claim(async_session, vault, other)

    out_of_range = await _hail(async_client, vault, other)
    assert out_of_range.status_code == 400, out_of_range.text
    self_hail = await _hail(async_client, vault, vault)
    assert self_hail.status_code == 400, self_hail.text

    await _visit(async_session, vault.id, slot_coords(theirs))
    assert (await _hail(async_client, vault, other)).status_code == 201
    duplicate = await _hail(async_client, vault, other)
    assert duplicate.status_code == 409, duplicate.text


async def test_being_hailed_waives_range_for_the_answer(
    async_client, owner, vault, user_with_vault, async_session
) -> None:
    other_user, other = user_with_vault
    mine, _theirs = await _claim(async_session, vault, other)
    await _visit(async_session, other.id, slot_coords(mine))

    app.dependency_overrides[get_current_active_user] = lambda: other_user
    assert (await _hail(async_client, other, vault)).status_code == 201

    app.dependency_overrides[get_current_active_user] = lambda: owner
    reach_back = await _hail(async_client, vault, other)  # no visit on this side at all
    assert reach_back.status_code == 201, reach_back.text


async def test_accepting_a_hail_opens_contact_and_pays_standing_once(
    async_client, owner, vault, user_with_vault, async_session
) -> None:
    other_user, other = user_with_vault
    _mine, theirs = await _claim(async_session, vault, other)
    await _visit(async_session, vault.id, slot_coords(theirs))
    filing_id = (await _hail(async_client, vault, other)).json()["filing_id"]

    app.dependency_overrides[get_current_active_user] = lambda: other_user
    accepted = await async_client.post(f"/vaults/{other.id}/envoy/filings/{filing_id}/respond", json={"accept": True})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "ACCEPTED"
    assert accepted.json()["responded_at"] is not None

    signal = _signal((await async_client.get(f"/vaults/{other.id}/envoy/signals")).json(), vault)
    assert signal["status"] == "CONTACT"
    assert signal["standing"] == 5
    assert signal["met_at"] is not None
    assert signal["can_hail"] is False

    app.dependency_overrides[get_current_active_user] = lambda: owner
    again = await _hail(async_client, vault, other)
    assert again.status_code == 409, again.text


async def test_refusing_locks_the_line_for_the_configured_hours(
    async_client, owner, vault, user_with_vault, async_session
) -> None:
    other_user, other = user_with_vault
    _mine, theirs = await _claim(async_session, vault, other)
    await _visit(async_session, vault.id, slot_coords(theirs))
    filing_id = (await _hail(async_client, vault, other)).json()["filing_id"]

    app.dependency_overrides[get_current_active_user] = lambda: other_user
    refused = await async_client.post(f"/vaults/{other.id}/envoy/filings/{filing_id}/respond", json={"accept": False})
    assert refused.status_code == 200, refused.text
    assert refused.json()["status"] == "REFUSED"

    signal = _signal((await async_client.get(f"/vaults/{other.id}/envoy/signals")).json(), vault)
    assert signal["status"] == "UNMET"
    assert signal["locked_until"] is not None
    assert _instant(signal["locked_until"]) > utcnow()

    app.dependency_overrides[get_current_active_user] = lambda: owner
    blocked = await _hail(async_client, vault, other)
    assert blocked.status_code == 409, blocked.text


async def test_an_overdue_filing_expires_on_read_and_cannot_be_answered(
    async_client, owner, vault, user_with_vault, async_session
) -> None:
    other_user, other = user_with_vault
    _mine, theirs = await _claim(async_session, vault, other)
    await _visit(async_session, vault.id, slot_coords(theirs))
    filing_id = (await _hail(async_client, vault, other)).json()["filing_id"]

    filing = (
        await async_session.execute(select(DiplomaticFiling).where(DiplomaticFiling.id == UUID(filing_id)))
    ).scalar_one()
    filing.expires_at = utcnow() - timedelta(hours=1)
    async_session.add(filing)
    await async_session.commit()

    app.dependency_overrides[get_current_active_user] = lambda: other_user
    late = await async_client.post(f"/vaults/{other.id}/envoy/filings/{filing_id}/respond", json={"accept": True})
    assert late.status_code == 400, late.text
    assert late.json()["detail"] == "This filing has expired."
    log = await async_client.get(f"/vaults/{other.id}/envoy/log")
    assert log.json()[0]["status"] == "EXPIRED"


async def test_crossed_hails_share_one_relation_and_pay_standing_once(
    async_client, owner, vault, user_with_vault, async_session
) -> None:
    other_user, other = user_with_vault
    mine, theirs = await _claim(async_session, vault, other)
    await _visit(async_session, vault.id, slot_coords(theirs))
    await _visit(async_session, other.id, slot_coords(mine))

    my_filing = (await _hail(async_client, vault, other)).json()["filing_id"]
    app.dependency_overrides[get_current_active_user] = lambda: other_user
    their_filing = (await _hail(async_client, other, vault)).json()["filing_id"]

    first = await async_client.post(f"/vaults/{other.id}/envoy/filings/{my_filing}/respond", json={"accept": True})
    assert first.status_code == 200, first.text

    app.dependency_overrides[get_current_active_user] = lambda: owner
    second = await async_client.post(f"/vaults/{vault.id}/envoy/filings/{their_filing}/respond", json={"accept": True})
    assert second.status_code == 200, second.text

    signal = _signal((await async_client.get(f"/vaults/{vault.id}/envoy/signals")).json(), other)
    assert signal["status"] == "CONTACT"
    assert signal["standing"] == 5


async def test_only_a_hail_is_filable_and_config_reports_the_effective_knobs(
    async_client, owner, vault, user_with_vault, async_session
) -> None:
    _other_user, other = user_with_vault
    _mine, theirs = await _claim(async_session, vault, other)
    await _visit(async_session, vault.id, slot_coords(theirs))

    accord = await async_client.post(
        f"/vaults/{vault.id}/envoy/filings", json={"to_vault_id": str(other.id), "kind": "ACCORD"}
    )
    assert accord.status_code == 400, accord.text

    config = await async_client.get(f"/vaults/{vault.id}/envoy/config")
    assert config.status_code == 200, config.text
    body = config.json()
    assert body["enabled"] is True
    assert body["trade_gate"] == "standoff"
    assert body["hail_radius"] == game_config.diplomacy.hail_radius
    assert body["filing_ttl_hours"] == game_config.diplomacy.filing_ttl_hours
    assert body["refusal_lock_hours"] == game_config.diplomacy.refusal_lock_hours
    assert body["stake_max"] == game_config.diplomacy.stake_max
