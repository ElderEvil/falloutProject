"""Tests for the retro-active bio place backfill script."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.dweller import Dweller
from app.schemas.common import AgeGroupEnum, DwellerStatusEnum, GenderEnum, RarityEnum
from scripts.backfill_dweller_bio_places import MAX_DWELLERS, _extract_places_from_bio
from scripts.backfill_dweller_bio_places import main as backfill_main


def _make_dweller(**overrides: object) -> Dweller:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "vault_id": uuid4(),
        "first_name": "Test",
        "last_name": "Dweller",
        "gender": GenderEnum.FEMALE,
        "rarity": RarityEnum.COMMON,
        "age_group": AgeGroupEnum.ADULT,
        "status": DwellerStatusEnum.IDLE,
        "level": 1,
        "strength": 1,
        "perception": 1,
        "endurance": 1,
        "charisma": 1,
        "intelligence": 1,
        "agility": 1,
        "luck": 1,
        "bio": None,
    }
    defaults.update(overrides)
    return Dweller(**defaults)


def _config_no_existing_locations(mock_session: AsyncMock) -> None:
    """Make session.execute() return a result whose .first() returns None."""
    mock_session.execute.return_value = MagicMock()
    mock_session.execute.return_value.first.return_value = None


def _config_has_existing_locations(mock_session: AsyncMock) -> None:
    """Make session.execute() return a result whose .first() returns a truthy row."""
    mock_session.execute.return_value = MagicMock()
    mock_session.execute.return_value.first.return_value = object()


# ---------------------------------------------------------------------------
# _extract_places_from_bio unit tests
# ---------------------------------------------------------------------------


def test_extract_no_bio_returns_none_empty():
    """No bio -> no origin, no visited."""
    origin, visited = _extract_places_from_bio(None)
    assert origin is None
    assert visited == []


def test_extract_empty_bio_returns_none_empty():
    """Empty bio string -> no matches."""
    origin, visited = _extract_places_from_bio("")
    assert origin is None
    assert visited == []


def test_extract_bio_with_no_known_places():
    """Bio text without any known place mentions -> skipped, no crash."""
    origin, visited = _extract_places_from_bio(
        "This dweller came from a small outpost and never went anywhere notable."
    )
    assert origin is None
    assert visited == []


def test_extract_origin_place_from_bio():
    """Bio containing a known origin place name is extracted."""
    origin, visited = _extract_places_from_bio(
        "Originally from Megaton, this dweller learned to survive early."
    )
    assert origin == "Megaton"
    assert visited == []


def test_extract_visited_place_from_bio():
    """Bio containing a known visited place name is extracted."""
    origin, visited = _extract_places_from_bio(
        "They once scavenged the Capital Wasteland and lived to tell the tale."
    )
    assert origin is None
    assert "the Capital Wasteland" in visited


def test_extract_origin_and_visited_from_bio():
    """Bio with both origin and visited places -> both extracted."""
    origin, visited = _extract_places_from_bio(
        "Hailing from Diamond City, this dweller wandered through the Commonwealth "
        "and survived a trip to Far Harbor."
    )
    assert origin == "Diamond City"
    assert "the Commonwealth" in visited
    assert "Far Harbor" in visited


def test_extract_multi_word_place():
    """Multi-word places like Starlight Drive-In are matched correctly."""
    origin, visited = _extract_places_from_bio(
        "They set up a trading post near Starlight Drive-In after leaving Sanctuary Hills."
    )
    assert origin == "Sanctuary Hills"
    assert "Starlight Drive-In" in visited


def test_extract_case_insensitive():
    """Place matching is case-insensitive."""
    origin, visited = _extract_places_from_bio(
        "born in megaton, travelled to the commonwealth."
    )
    assert origin == "Megaton"
    assert "the Commonwealth" in visited


def test_extract_does_not_match_partial_words():
    """Regex word-boundary: 'Megaton' does NOT match inside 'Megatonia'."""
    origin, visited = _extract_places_from_bio(
        "The Megatonia settlement was prosperous but nothing like Megaton itself."
    )
    assert origin == "Megaton"
    assert visited == []


def test_extract_visited_with_leading_space_in_list():
    """Places like ' Zion Canyon' (with leading space in _VISITED_PLACES) match in bio text."""
    origin, visited = _extract_places_from_bio(
        "They survived Zion Canyon and brought back useful herbs."
    )
    assert origin is None
    assert "Zion Canyon" in visited


def test_extract_place_in_both_lists_treated_as_origin():
    """Places in both origin and visited lists -> treated as origin, not duplicated."""
    origin, visited = _extract_places_from_bio(
        "From Sanctuary Hills, they dreamed of returning to Sanctuary Hills one day."
    )
    assert origin == "Sanctuary Hills"
    assert "Sanctuary Hills" not in visited


def test_extract_multiple_visited_deduped():
    """Repeated place mentions -> deduplicated in visited list."""
    origin, visited = _extract_places_from_bio(
        "They went to Far Harbor, then Far Harbor again, and also Far Harbor."
    )
    assert origin is None
    assert visited == ["Far Harbor"]


# ---------------------------------------------------------------------------
# main() integration tests (with mocks)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_main_no_bio_dweller_skipped():
    """Dweller with no bio is skipped entirely."""
    vault_id = uuid4()
    dweller_obj = _make_dweller(vault_id=vault_id, bio=None)
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session

    with (
        patch("scripts.backfill_dweller_bio_places.async_session_maker", return_value=mock_session),
        patch("scripts.backfill_dweller_bio_places.crud.vault.get", new_callable=AsyncMock) as mock_vault_get,
        patch(
            "scripts.backfill_dweller_bio_places.crud.dweller.get_multi_by_vault",
            new_callable=AsyncMock,
        ) as mock_get_dwellers,
        patch(
            "scripts.backfill_dweller_bio_places.map_service.register_bio_places",
            new_callable=AsyncMock,
        ) as mock_reg,
    ):
        mock_vault_get.return_value = type("Vault", (), {"id": vault_id})()
        mock_get_dwellers.return_value = [dweller_obj]

        await backfill_main(vault_uuid=str(vault_id), max_dwellers=MAX_DWELLERS)

        mock_reg.assert_not_called()


@pytest.mark.asyncio
async def test_main_calls_register_bio_places_with_extracted_places():
    """Dweller with bio containing known places -> register_bio_places called correctly."""
    vault_id = uuid4()
    dweller_obj = _make_dweller(
        vault_id=vault_id,
        bio="Originally from Megaton, this dweller scavenged the Capital Wasteland and Far Harbor.",
    )
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    _config_no_existing_locations(mock_session)

    with (
        patch("scripts.backfill_dweller_bio_places.async_session_maker", return_value=mock_session),
        patch("scripts.backfill_dweller_bio_places.crud.vault.get", new_callable=AsyncMock) as mock_vault_get,
        patch(
            "scripts.backfill_dweller_bio_places.crud.dweller.get_multi_by_vault",
            new_callable=AsyncMock,
        ) as mock_get_dwellers,
        patch(
            "scripts.backfill_dweller_bio_places.map_service.register_bio_places",
            new_callable=AsyncMock,
        ) as mock_reg,
    ):
        mock_vault_get.return_value = type("Vault", (), {"id": vault_id})()
        mock_get_dwellers.return_value = [dweller_obj]

        await backfill_main(vault_uuid=str(vault_id), max_dwellers=MAX_DWELLERS)

        mock_reg.assert_called_once()
        call_args = mock_reg.call_args
        assert call_args[0][0] is mock_session
        assert call_args[0][1] is dweller_obj
        assert call_args[1]["origin_place"] == "Megaton"
        assert "the Capital Wasteland" in call_args[1]["visited_places"]
        assert "Far Harbor" in call_args[1]["visited_places"]


@pytest.mark.asyncio
async def test_main_register_bio_places_failure_is_swallowed():
    """When register_bio_places raises, the script continues and does NOT crash."""
    vault_id = uuid4()
    dweller_bad = _make_dweller(
        vault_id=vault_id,
        bio="From Megaton, they explored Far Harbor.",
    )
    dweller_ok = _make_dweller(
        vault_id=vault_id,
        bio="From Diamond City, they roamed the Commonwealth.",
    )
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    _config_no_existing_locations(mock_session)

    with (
        patch("scripts.backfill_dweller_bio_places.async_session_maker", return_value=mock_session),
        patch("scripts.backfill_dweller_bio_places.crud.vault.get", new_callable=AsyncMock) as mock_vault_get,
        patch(
            "scripts.backfill_dweller_bio_places.crud.dweller.get_multi_by_vault",
            new_callable=AsyncMock,
        ) as mock_get_dwellers,
        patch(
            "scripts.backfill_dweller_bio_places.map_service.register_bio_places",
            new_callable=AsyncMock,
        ) as mock_reg,
    ):
        mock_vault_get.return_value = type("Vault", (), {"id": vault_id})()
        mock_get_dwellers.return_value = [dweller_bad, dweller_ok]
        mock_reg.side_effect = [Exception("DB error"), None]

        # Must NOT raise
        await backfill_main(vault_uuid=str(vault_id), max_dwellers=MAX_DWELLERS)

        assert mock_reg.call_count == 2


@pytest.mark.asyncio
async def test_main_vault_not_found_graceful():
    """Non-existent vault UUID -> exits gracefully, no crash."""
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session

    with (
        patch("scripts.backfill_dweller_bio_places.async_session_maker", return_value=mock_session),
        patch("scripts.backfill_dweller_bio_places.crud.vault.get", new_callable=AsyncMock) as mock_vault_get,
        patch(
            "scripts.backfill_dweller_bio_places.map_service.register_bio_places",
            new_callable=AsyncMock,
        ) as mock_reg,
    ):
        mock_vault_get.return_value = None

        await backfill_main(vault_uuid=str(uuid4()), max_dwellers=MAX_DWELLERS)

        mock_reg.assert_not_called()


@pytest.mark.asyncio
async def test_main_vault_filter_restricts_scope():
    """Only dwellers in the specified vault are processed."""
    vault_a = uuid4()
    dweller_a = _make_dweller(vault_id=vault_a, bio="From Megaton.")
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    _config_no_existing_locations(mock_session)

    with (
        patch("scripts.backfill_dweller_bio_places.async_session_maker", return_value=mock_session),
        patch("scripts.backfill_dweller_bio_places.crud.vault.get", new_callable=AsyncMock) as mock_vault_get,
        patch(
            "scripts.backfill_dweller_bio_places.crud.dweller.get_multi_by_vault",
            new_callable=AsyncMock,
        ) as mock_get_dwellers,
        patch(
            "scripts.backfill_dweller_bio_places.map_service.register_bio_places",
            new_callable=AsyncMock,
        ) as mock_reg,
    ):
        mock_vault_get.return_value = type("Vault", (), {"id": vault_a})()
        mock_get_dwellers.return_value = [dweller_a]

        await backfill_main(vault_uuid=str(vault_a), max_dwellers=MAX_DWELLERS)

        mock_reg.assert_called_once()
        call_args = mock_reg.call_args
        assert call_args[0][1] is dweller_a


@pytest.mark.asyncio
async def test_main_skips_dwellers_with_existing_locations():
    """Dwellers that already have DwellerLocation rows are skipped."""
    vault_id = uuid4()
    dweller_obj = _make_dweller(
        vault_id=vault_id,
        bio="From Megaton, wandered the Commonwealth.",
    )
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    _config_has_existing_locations(mock_session)

    with (
        patch("scripts.backfill_dweller_bio_places.async_session_maker", return_value=mock_session),
        patch("scripts.backfill_dweller_bio_places.crud.vault.get", new_callable=AsyncMock) as mock_vault_get,
        patch(
            "scripts.backfill_dweller_bio_places.crud.dweller.get_multi_by_vault",
            new_callable=AsyncMock,
        ) as mock_get_dwellers,
        patch(
            "scripts.backfill_dweller_bio_places.map_service.register_bio_places",
            new_callable=AsyncMock,
        ) as mock_reg,
    ):
        mock_vault_get.return_value = type("Vault", (), {"id": vault_id})()
        mock_get_dwellers.return_value = [dweller_obj]

        await backfill_main(vault_uuid=str(vault_id), max_dwellers=MAX_DWELLERS)

        mock_reg.assert_not_called()
