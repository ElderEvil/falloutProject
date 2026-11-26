from datetime import timedelta
from uuid import uuid4

import pytest
from sqlmodel import select

from app import crud
from app.core.enums import DwellerLocationRelationEnum, ExplorationStatus
from app.crud.vault_slot import vault_slot
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.team import Team, TeamMember
from app.models.world_location import VaultLocationState, WorldLocation
from app.schemas.vault import VaultCreateWithUserID
from app.services.exploration_service import exploration_service
from app.services.map_service import map_service
from app.tests.factory.dwellers import create_fake_dweller
from app.utils.time import utcnow

SPECIAL = ("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck")


async def _claim_slot(session, vault) -> None:
    # Dispatches originate from the vault's slot placement; claim one.
    await vault_slot.claim_next(db_session=session, vault_id=vault.id)
    await session.commit()


async def _send(session, vault, dweller, **kwargs) -> Exploration:
    return await exploration_service.send_dweller(session, vault.id, dweller.id, duration=4, **kwargs)


async def _red_rock_state(session, vault, dweller) -> VaultLocationState:
    await map_service.register_bio_places(session, dweller, origin_place="Red Rocket", visited_places=[])
    result = await session.execute(
        select(VaultLocationState)
        .join(WorldLocation, WorldLocation.id == VaultLocationState.location_id)
        .where(VaultLocationState.vault_id == vault.id, WorldLocation.name == "Red Rocket")
    )
    return result.scalar_one()


async def _target_ready(session, vault, dweller) -> VaultLocationState:
    await _claim_slot(session, vault)
    state = await _red_rock_state(session, vault, dweller)
    await crud.world_location.link_dweller(
        session, dweller.id, state.location_id, DwellerLocationRelationEnum.VISITED, is_unlocked=True
    )
    return state


async def _arrived(session, run) -> None:
    # Arrival finalizes the return leg; pretend the travel time elapsed.
    run.return_completes_at = utcnow() - timedelta(seconds=1)
    session.add(run)
    await session.commit()


async def _make_exploration(session, vault, anchor) -> Exploration:
    run = Exploration(
        dweller_id=anchor.id,
        vault_id=vault.id,
        duration=4,
        **{f"dweller_{stat}": 5 for stat in SPECIAL},
    )
    session.add(run)
    await session.commit()
    return run


async def _attach_dispatch_team(session, vault, run, dwellers) -> Team:
    team = Team(vault_id=vault.id, exploration_id=run.id)
    session.add(team)
    await session.flush()
    session.add_all(
        [
            TeamMember(team_id=team.id, dweller_id=dweller.id, slot_number=slot, status="assigned")
            for slot, dweller in enumerate(dwellers, start=1)
        ]
    )
    run.team_id = team.id
    session.add(run)
    await session.commit()
    return team


@pytest.mark.smoke
async def test_send_dweller_to_wasteland_success(
    async_client, superuser_token_headers, async_session, vault, dweller, room
) -> None:
    dweller.room_id = room.id
    await async_session.commit()
    response = await async_client.post(
        f"/explorations/send?vault_id={vault.id}",
        json={"dweller_id": str(dweller.id), "duration": 4},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["dweller_id"] == str(dweller.id)
    assert data["vault_id"] == str(vault.id)
    assert data["status"] == ExplorationStatus.ACTIVE
    assert data["duration"] == 4

    # SPECIAL stats are captured on the run.
    assert tuple(data[f"dweller_{stat}"] for stat in SPECIAL) == tuple(getattr(dweller, stat) for stat in SPECIAL)

    assert data["total_distance"] == 0
    assert data["total_caps_found"] == 0
    assert data["enemies_encountered"] == 0
    assert data["events"] == []
    assert data["loot_collected"] == []
    await async_session.refresh(dweller)
    assert dweller.room_id is None


async def test_send_routes_to_clear_when_target_given(
    async_client, superuser_token_headers, async_session, vault, dweller
) -> None:
    state = await _target_ready(async_session, vault, dweller)
    response = await async_client.post(
        f"/explorations/send?vault_id={vault.id}",
        json={"dweller_ids": [str(dweller.id)], "target_location_id": str(state.location_id)},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["target_location_id"] == str(state.location_id)

    run = await crud.exploration.get_by_dweller(async_session, dweller_id=dweller.id)
    assert run is not None
    assert run.target_location_id == state.location_id
    assert run.team_id is not None


async def test_send_validates_roster(async_client, superuser_token_headers, vault, dweller) -> None:
    dweller_id = str(dweller.id)
    for payload, status in (
        ({"dweller_ids": [dweller_id, dweller_id]}, 400),
        ({"duration": 4}, 400),
        ({"dweller_id": dweller_id, "dweller_ids": [dweller_id]}, 422),
    ):
        response = await async_client.post(
            f"/explorations/send?vault_id={vault.id}", json=payload, headers=superuser_token_headers
        )
        assert response.status_code == status


async def test_send_rejects_locked_target(async_client, superuser_token_headers, async_session, vault, dweller) -> None:
    state = await _red_rock_state(async_session, vault, dweller)
    response = await async_client.post(
        f"/explorations/send?vault_id={vault.id}",
        json={"dweller_ids": [str(dweller.id)], "target_location_id": str(state.location_id)},
        headers=superuser_token_headers,
    )
    assert response.status_code == 400


async def test_list_explorations_empty(async_client, superuser_token_headers, vault) -> None:
    response = await async_client.get(
        f"/explorations/vault/{vault.id}?active_only=true", headers=superuser_token_headers
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_dispatch_dweller_success_and_listing(
    async_client, superuser_token_headers, async_session, vault, dweller
) -> None:
    state = await _target_ready(async_session, vault, dweller)
    response = await async_client.post(
        f"/explorations/dispatch?vault_id={vault.id}",
        json={"dweller_ids": [str(dweller.id)], "location_id": str(state.location_id)},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["dweller_id"] == str(dweller.id)
    assert data["vault_id"] == str(vault.id)
    assert data["status"] == ExplorationStatus.ACTIVE
    assert data["target_location_id"] == str(state.location_id)

    run = await crud.exploration.get_by_dweller(async_session, dweller_id=dweller.id)
    assert run is not None
    assert run.target_location_id == state.location_id
    assert run.clear_tier == 0
    assert run.team_id is not None

    listed = await async_client.get(f"/explorations/vault/{vault.id}?active_only=true", headers=superuser_token_headers)
    assert listed.status_code == 200
    payload = listed.json()
    assert len(payload) == 1
    assert payload[0]["target_location_id"] == str(state.location_id)


async def test_list_explorations_includes_paused_at(
    async_client, superuser_token_headers, async_session, vault, dweller
) -> None:
    run = await _send(async_session, vault, dweller)
    run.paused_at = utcnow()
    async_session.add(run)
    await async_session.commit()

    response = await async_client.get(
        f"/explorations/vault/{vault.id}?active_only=true", headers=superuser_token_headers
    )
    assert response.status_code == 200
    row = next(item for item in response.json() if item["id"] == str(run.id))
    assert row["paused_at"] is not None


async def test_get_exploration_details_reports_pack_capacity(
    async_client, superuser_token_headers, async_session, vault, dweller
) -> None:
    run = await _send(async_session, vault, dweller)
    run.dweller_strength = 3
    run.add_loot(item_name="Desk Fan", quantity=2, rarity="Common", item_type="junk")
    run.add_loot(item_name="Stimpak", rarity="Common", item_type="stimpak")
    async_session.add(run)
    await async_session.commit()
    await crud.exploration.add_event(
        async_session,
        exploration_id=run.id,
        event_type="loot_found",
        description="Found a cool item",
        loot={"item": {"name": "Desk Fan", "rarity": "Common", "value": 10}, "caps": 15},
    )

    response = await async_client.get(f"/explorations/{run.id}", headers=superuser_token_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(run.id)
    assert data["dweller_strength"] == 3
    # 15 + 2 * 3; the stimpak rides in the pouch and the Desk Fan stack takes two slots.
    assert data["carry_capacity"] == 21
    assert data["pack_slots_used"] == 2
    assert [event["description"] for event in data["events"]] == ["Found a cool item"]


async def test_list_explorations_reports_pack_and_activity(
    async_client, superuser_token_headers, async_session, vault, dweller
) -> None:
    """The list payload feeds the explorer card; it must carry loot, events and pack figures."""
    run = await _send(async_session, vault, dweller)
    run.dweller_strength = 3
    run.add_loot(item_name="Desk Fan", quantity=2, rarity="Common", item_type="junk")
    run.add_loot(item_name="Stimpak", rarity="Common", item_type="stimpak")
    async_session.add(run)
    await async_session.commit()
    await crud.exploration.add_event(
        async_session,
        exploration_id=run.id,
        event_type="loot_found",
        description="Found a cool item",
        loot={"item": {"name": "Desk Fan", "rarity": "Common", "value": 10}, "caps": 15},
    )

    response = await async_client.get(
        f"/explorations/vault/{vault.id}?active_only=true", headers=superuser_token_headers
    )

    assert response.status_code == 200
    row = next(item for item in response.json() if item["id"] == str(run.id))
    assert row["dweller_strength"] == 3
    assert row["carry_capacity"] == 21
    assert row["pack_slots_used"] == 2
    assert [item["item_name"] for item in row["loot_collected"]] == ["Desk Fan", "Stimpak"]
    assert [event["description"] for event in row["events"]] == ["Found a cool item"]


async def test_get_exploration_progress(async_client, superuser_token_headers, async_session, vault, dweller) -> None:
    run = await _send(async_session, vault, dweller)
    response = await async_client.get(f"/explorations/{run.id}/progress", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(run.id)
    assert data["status"] == ExplorationStatus.ACTIVE
    for field in ("progress_percentage", "time_remaining_seconds", "elapsed_time_seconds", "events", "loot_collected"):
        assert field in data
    assert 0 <= data["progress_percentage"] <= 100


@pytest.mark.parametrize(
    ("recalled", "distance", "enemies", "terminal"),
    [(True, 10, 2, ExplorationStatus.RECALLED), (False, 50, 5, ExplorationStatus.COMPLETED)],
)
async def test_recall_and_complete_pay_only_on_arrival(
    async_client, superuser_token_headers, async_session, vault, dweller, recalled, distance, enemies, terminal
) -> None:
    run = await _send(async_session, vault, dweller)
    await crud.exploration.add_loot(
        async_session, exploration_id=run.id, item_name="Desk Fan", quantity=1, rarity="Rare"
    )
    run = await crud.exploration.update_stats(
        async_session, exploration_id=run.id, caps=100, distance=distance, enemies=enemies
    )
    if not recalled:
        run.start_time = utcnow() - timedelta(hours=run.duration)
        async_session.add(run)
        await async_session.commit()
    initial_caps = vault.bottle_caps

    action = "recall" if recalled else "complete"
    response = await async_client.post(f"/explorations/{run.id}/{action}", json={}, headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    # The action only starts the return leg: no rewards and no loot until arrival.
    assert data["exploration"]["status"] == ExplorationStatus.RETURNING
    assert data["exploration"]["return_completes_at"] is not None
    assert data["rewards_summary"] is None

    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps

    await async_session.refresh(run)
    await _arrived(async_session, run)
    arrival = await async_client.post(f"/explorations/{run.id}/complete", json={}, headers=superuser_token_headers)
    assert arrival.status_code == 200
    arrival_data = arrival.json()
    assert arrival_data["exploration"]["status"] == terminal
    assert arrival_data["exploration"]["end_time"] is not None
    rewards = arrival_data["rewards_summary"]
    assert (rewards["caps"], rewards["distance"], rewards["enemies_defeated"]) == (100, distance, enemies)
    assert bool(rewards.get("recalled_early")) is recalled
    if recalled:
        assert "progress_percentage" in rewards
    else:
        assert rewards["experience"] > 0

    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 100


async def test_generate_event_success(async_client, superuser_token_headers, async_session, vault, dweller) -> None:
    run = await _send(async_session, vault, dweller)
    response = await async_client.post(
        f"/explorations/{run.id}/generate_event", json={}, headers=superuser_token_headers
    )
    assert response.status_code == 200
    # Event generation is probabilistic; the run itself is always returned.
    assert response.json()["id"] == str(run.id)


async def test_get_exploration_party_returns_slot_ordered_members(
    async_client, superuser_token_headers, async_session, vault, dweller
) -> None:
    party = [
        dweller,
        Dweller(**create_fake_dweller(), vault_id=vault.id),
        Dweller(**create_fake_dweller(), vault_id=vault.id),
    ]
    async_session.add_all(party[1:])
    await async_session.commit()
    run = await _make_exploration(async_session, vault, dweller)
    await _attach_dispatch_team(async_session, vault, run, party)

    response = await async_client.get(f"/explorations/vault/{vault.id}/{run.id}/party", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert [member["slot_number"] for member in data] == [1, 2, 3]
    assert [member["dweller_id"] for member in data] == [str(d.id) for d in party]
    assert data[0]["exploration_id"] == str(run.id)
    assert data[0]["vault_id"] == str(vault.id)
    assert data[0]["status"] == "assigned"


@pytest.mark.parametrize(
    ("as_superuser", "foreign_vault", "expected"),
    [(True, False, 404), (True, True, 404), (False, False, 403)],
)
async def test_get_exploration_party_rejects_missing_run_or_foreign_access(
    async_client,
    async_session,
    vault,
    dweller,
    vault_data,
    superuser,
    superuser_token_headers,
    normal_user_token_headers,
    as_superuser,
    foreign_vault,
    expected,
) -> None:
    run = await _make_exploration(async_session, vault, dweller)
    target_vault = vault
    if foreign_vault:
        target_vault = await crud.vault.create(
            async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=superuser.id)
        )
    run_id = uuid4() if not foreign_vault and as_superuser else run.id
    response = await async_client.get(
        f"/explorations/vault/{target_vault.id}/{run_id}/party",
        headers=superuser_token_headers if as_superuser else normal_user_token_headers,
    )
    assert response.status_code == expected


async def test_get_exploration_party_empty_for_free_roam_run(
    async_client, superuser_token_headers, async_session, vault, dweller
) -> None:
    run = await _make_exploration(async_session, vault, dweller)
    response = await async_client.get(f"/explorations/vault/{vault.id}/{run.id}/party", headers=superuser_token_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_complete_before_duration_returns_400(
    async_client, superuser_token_headers, async_session, vault, dweller
) -> None:
    run = await _send(async_session, vault, dweller)
    response = await async_client.post(f"/explorations/{run.id}/complete", json={}, headers=superuser_token_headers)
    assert response.status_code == 400
    assert "has not finished yet" in response.json()["detail"].lower()
    await async_session.refresh(run)
    assert run.status == ExplorationStatus.ACTIVE


async def test_complete_and_recall_finished_exploration_returns_400(
    async_client, superuser_token_headers, async_session, vault, dweller
) -> None:
    run = await _send(async_session, vault, dweller)
    await exploration_service.recall_exploration_with_data(async_session, run.id)
    await async_session.refresh(run)
    await _arrived(async_session, run)
    await exploration_service.complete_exploration_with_data(async_session, run.id)
    await async_session.refresh(run)
    assert run.status != ExplorationStatus.ACTIVE

    for action in ("recall", "complete"):
        response = await async_client.post(f"/explorations/{run.id}/{action}", json={}, headers=superuser_token_headers)
        assert response.status_code == 400
        assert "not active" in response.json()["detail"].lower()
