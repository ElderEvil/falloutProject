"""Tests for DwellerAIService world-map place extraction (bio → markers)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.dweller_ai import DwellerBackstory, ExtendedBio
from app.services.dweller_ai import BIO_DB_MAX_LENGTH, dweller_ai

pytestmark = pytest.mark.asyncio


def _make_dweller_mock(bio: str | None = None) -> MagicMock:
    """Return a MagicMock with the minimum DwellerReadFull shape needed."""
    dweller = MagicMock()
    dweller.bio = bio
    dweller.id = uuid.uuid4()
    dweller.first_name = "Test"
    dweller.gender = "male"
    dweller.vault_id = uuid.uuid4()
    dweller.strength = 5
    dweller.perception = 5
    dweller.endurance = 5
    dweller.charisma = 5
    dweller.intelligence = 5
    dweller.agility = 5
    dweller.luck = 5
    dweller.rarity = "common"
    return dweller


# ── generate_backstory ────────────────────────────────────────────


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.map_service")
@patch("app.services.dweller_ai.dweller_crud")
@patch("app.services.dweller_ai.backstory_agent")
@patch("app.services.dweller_ai.quota_service")
async def test_generate_backstory_registers_origin_and_visited(
    mock_quota: MagicMock,
    mock_agent: MagicMock,
    mock_crud: MagicMock,
    mock_map: MagicMock,
    mock_llm: MagicMock,
) -> None:
    """Backstory with origin_place='Megaton' + 2 visited places → map markers created."""
    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))
    mock_llm.create = AsyncMock()
    mock_crud.update = AsyncMock()
    mock_map.register_bio_places = AsyncMock()

    mock_dweller = _make_dweller_mock(bio=None)

    # backstory agent output
    output = DwellerBackstory(
        bio="A test backstory.",
        origin_place="Megaton",
        visited_places=["Rivet City", "Goodneighbor"],
    )
    mock_result = MagicMock()
    mock_result.output = output
    mock_result.usage.return_value = MagicMock(input_tokens=100, output_tokens=50, total_tokens=150)
    mock_agent.run = AsyncMock(return_value=mock_result)

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    result = await dweller_ai.generate_backstory(
        user=mock_user,
        db_session=MagicMock(),
        dweller_info=mock_dweller,
        origin=None,
    )

    # map_service called with correct args
    mock_map.register_bio_places.assert_called_once()
    call_kwargs = mock_map.register_bio_places.call_args[1]
    assert call_kwargs["origin_place"] == "Megaton"
    assert call_kwargs["visited_places"] == ["Rivet City", "Goodneighbor"]
    assert call_kwargs["explicit_origin"] is None

    # exactly one LLMInteraction created
    mock_llm.create.assert_called_once()

    # bio was updated
    mock_crud.update.assert_called_once()
    assert result is mock_dweller


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.map_service")
@patch("app.services.dweller_ai.dweller_crud")
@patch("app.services.dweller_ai.backstory_agent")
@patch("app.services.dweller_ai.quota_service")
async def test_generate_backstory_explicit_origin_overrides_llm(
    mock_quota: MagicMock,
    mock_agent: MagicMock,
    mock_crud: MagicMock,
    mock_map: MagicMock,
    mock_llm: MagicMock,
) -> None:
    """explicit_origin='Junktown' is passed through, overriding LLM origin_place."""
    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))
    mock_llm.create = AsyncMock()
    mock_crud.update = AsyncMock()
    mock_map.register_bio_places = AsyncMock()

    mock_dweller = _make_dweller_mock(bio=None)

    output = DwellerBackstory(
        bio="Backstory.",
        origin_place="Somewhere",
        visited_places=[],
    )
    mock_result = MagicMock()
    mock_result.output = output
    mock_result.usage.return_value = MagicMock(input_tokens=50, output_tokens=20, total_tokens=70)
    mock_agent.run = AsyncMock(return_value=mock_result)

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    await dweller_ai.generate_backstory(
        user=mock_user,
        db_session=MagicMock(),
        dweller_info=mock_dweller,
        origin="Junktown",
    )

    call_kwargs = mock_map.register_bio_places.call_args[1]
    assert call_kwargs["origin_place"] == "Somewhere"
    assert call_kwargs["explicit_origin"] == "Junktown"


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.map_service")
@patch("app.services.dweller_ai.dweller_crud")
@patch("app.services.dweller_ai.backstory_agent")
@patch("app.services.dweller_ai.quota_service")
async def test_generate_backstory_llm_origin_wasteland_still_calls_map(
    mock_quota: MagicMock,
    mock_agent: MagicMock,
    mock_crud: MagicMock,
    mock_map: MagicMock,
    mock_llm: MagicMock,
) -> None:
    """LLM origin_place='Wasteland' is still passed to map_service (skip-list handles it)."""
    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))
    mock_llm.create = AsyncMock()
    mock_crud.update = AsyncMock()
    mock_map.register_bio_places = AsyncMock()

    mock_dweller = _make_dweller_mock(bio=None)

    output = DwellerBackstory(
        bio="Backstory.",
        origin_place="Wasteland",
        visited_places=["Megaton"],
    )
    mock_result = MagicMock()
    mock_result.output = output
    mock_result.usage.return_value = MagicMock(input_tokens=30, output_tokens=10, total_tokens=40)
    mock_agent.run = AsyncMock(return_value=mock_result)

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    result = await dweller_ai.generate_backstory(
        user=mock_user,
        db_session=MagicMock(),
        dweller_info=mock_dweller,
    )

    # map_service IS called — it decides to skip internally via _should_skip
    mock_map.register_bio_places.assert_called_once()
    call_kwargs = mock_map.register_bio_places.call_args[1]
    assert call_kwargs["origin_place"] == "Wasteland"
    assert call_kwargs["visited_places"] == ["Megaton"]

    # bio call still succeeded
    mock_crud.update.assert_called_once()
    mock_llm.create.assert_called_once()
    assert result is not None


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.map_service")
@patch("app.services.dweller_ai.dweller_crud")
@patch("app.services.dweller_ai.backstory_agent")
@patch("app.services.dweller_ai.quota_service")
async def test_generate_backstory_map_service_raising_is_swallowed(
    mock_quota: MagicMock,
    mock_agent: MagicMock,
    mock_crud: MagicMock,
    mock_map: MagicMock,
    mock_llm: MagicMock,
) -> None:
    """When map_service raises, the bio generation still succeeds (best-effort)."""
    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))
    mock_llm.create = AsyncMock()
    mock_crud.update = AsyncMock()
    mock_map.register_bio_places = AsyncMock(side_effect=Exception("DB failure"))

    mock_dweller = _make_dweller_mock(bio=None)

    output = DwellerBackstory(
        bio="Backstory.",
        origin_place="Megaton",
        visited_places=["Rivet City"],
    )
    mock_result = MagicMock()
    mock_result.output = output
    mock_result.usage.return_value = MagicMock(input_tokens=30, output_tokens=10, total_tokens=40)
    mock_agent.run = AsyncMock(return_value=mock_result)

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    # Should NOT raise — helper catches internally
    result = await dweller_ai.generate_backstory(
        user=mock_user,
        db_session=MagicMock(),
        dweller_info=mock_dweller,
    )

    # Bio was still committed
    mock_crud.update.assert_called_once()
    mock_llm.create.assert_called_once()
    assert result is not None


# ── extend_bio ─────────────────────────────────────────────────────


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.map_service")
@patch("app.services.dweller_ai.dweller_crud")
@patch("app.services.dweller_ai.bio_extension_agent")
@patch("app.services.dweller_ai.quota_service")
async def test_extend_bio_registers_visited_places(
    mock_quota: MagicMock,
    mock_agent: MagicMock,
    mock_crud: MagicMock,
    mock_map: MagicMock,
    mock_llm: MagicMock,
) -> None:
    """extend_bio with visited_places=['Junktown'] → map markers created."""
    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))
    mock_llm.create = AsyncMock()
    mock_crud.update = AsyncMock()
    mock_map.register_bio_places = AsyncMock()

    mock_dweller = _make_dweller_mock(bio="Existing bio for extension.")
    mock_crud.get_full_info = AsyncMock(return_value=mock_dweller)

    output = ExtendedBio(
        extended_bio="More details about travels.",
        visited_places=["Junktown"],
    )
    mock_result = MagicMock()
    mock_result.output = output
    mock_result.usage.return_value = MagicMock(input_tokens=40, output_tokens=20, total_tokens=60)
    mock_agent.run = AsyncMock(return_value=mock_result)

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    result = await dweller_ai.extend_bio(
        db_session=MagicMock(),
        dweller_id=mock_dweller.id,
        user=mock_user,
    )

    mock_map.register_bio_places.assert_called_once()
    call_kwargs = mock_map.register_bio_places.call_args[1]
    assert call_kwargs["visited_places"] == ["Junktown"]
    assert call_kwargs["origin_place"] == ""

    mock_crud.update.assert_called_once()
    mock_llm.create.assert_called_once()
    assert result is not None


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.map_service")
@patch("app.services.dweller_ai.dweller_crud")
@patch("app.services.dweller_ai.bio_extension_agent")
@patch("app.services.dweller_ai.quota_service")
async def test_extend_bio_length_guard_truncates_at_1024(
    mock_quota: MagicMock,
    mock_agent: MagicMock,
    mock_crud: MagicMock,
    mock_map: MagicMock,
    mock_llm: MagicMock,
) -> None:
    """Bio of 950 chars + 300-char extension → stored bio ≤ 1024, ends with '...'."""
    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))
    mock_llm.create = AsyncMock()
    mock_map.register_bio_places = AsyncMock()

    # 950-char existing bio
    existing_bio = "A" * 950
    mock_dweller = _make_dweller_mock(bio=existing_bio)
    mock_crud.get_full_info = AsyncMock(return_value=mock_dweller)
    mock_crud.update = AsyncMock()

    # 300-char extension (combined = 1250 > 1024)
    output = ExtendedBio(
        extended_bio="B" * 300,
        visited_places=[],
    )
    mock_result = MagicMock()
    mock_result.output = output
    mock_result.usage.return_value = MagicMock(input_tokens=40, output_tokens=20, total_tokens=60)
    mock_agent.run = AsyncMock(return_value=mock_result)

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    await dweller_ai.extend_bio(
        db_session=MagicMock(),
        dweller_id=mock_dweller.id,
        user=mock_user,
    )

    # The bio passed to crud.update should be truncated
    mock_crud.update.assert_called_once()
    update_call = mock_crud.update.call_args
    stored_bio = update_call[0][2].bio  # DwellerUpdate.bio
    assert len(stored_bio) <= BIO_DB_MAX_LENGTH
    assert stored_bio.endswith("...")
    assert not stored_bio.endswith("....")  # not double-truncated


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.map_service")
@patch("app.services.dweller_ai.dweller_crud")
@patch("app.services.dweller_ai.bio_extension_agent")
@patch("app.services.dweller_ai.quota_service")
async def test_extend_bio_map_service_raising_is_swallowed(
    mock_quota: MagicMock,
    mock_agent: MagicMock,
    mock_crud: MagicMock,
    mock_map: MagicMock,
    mock_llm: MagicMock,
) -> None:
    """When map_service raises, extend_bio still succeeds (best-effort)."""
    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))
    mock_llm.create = AsyncMock()
    mock_map.register_bio_places = AsyncMock(side_effect=Exception("DB failure"))

    mock_dweller = _make_dweller_mock(bio="Existing bio.")
    mock_crud.get_full_info = AsyncMock(return_value=mock_dweller)
    mock_crud.update = AsyncMock()

    output = ExtendedBio(
        extended_bio="Extended details.",
        visited_places=["Junktown"],
    )
    mock_result = MagicMock()
    mock_result.output = output
    mock_result.usage.return_value = MagicMock(input_tokens=30, output_tokens=10, total_tokens=40)
    mock_agent.run = AsyncMock(return_value=mock_result)

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    # Should NOT raise
    result = await dweller_ai.extend_bio(
        db_session=MagicMock(),
        dweller_id=mock_dweller.id,
        user=mock_user,
    )

    mock_crud.update.assert_called_once()
    mock_llm.create.assert_called_once()
    assert result is not None
