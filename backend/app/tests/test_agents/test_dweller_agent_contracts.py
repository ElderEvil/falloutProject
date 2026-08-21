"""Deterministic contract tests for the stateless dweller Pydantic AI agents."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic_ai.exceptions import ModelRetry, UnexpectedModelBehavior
from pydantic_ai.models.test import TestModel

from app.agents.dweller_agents import backstory_agent, bio_extension_agent, visual_attributes_agent
from app.agents.dweller_chat_agent import (
    DwellerActivityBriefing,
    DwellerChatDeps,
    DwellerChatOutput,
    build_dweller_social_context,
    dweller_chat_agent,
    parse_action_suggestion,
    validate_dweller_chat_output,
)
from app.schemas.chat import NoAction
from app.schemas.common import DwellerStatusEnum, SPECIALEnum


def _make_dweller() -> MagicMock:
    """Return the smallest realistic dweller shape required by dynamic instructions."""
    dweller = MagicMock()
    dweller.first_name = "Casey"
    dweller.last_name = "Jones"
    dweller.gender.value = "female"
    dweller.age_group.value = "adult"
    dweller.level = 7
    dweller.rarity.value = "common"
    dweller.vault.number = 13
    dweller.vault.happiness = 75
    dweller.vault.power = dweller.vault.power_max = 100
    dweller.vault.food = dweller.vault.food_max = 100
    dweller.vault.water = dweller.vault.water_max = 100
    dweller.room = None
    dweller.outfit = None
    dweller.weapon = None
    dweller.health = dweller.max_health = 100
    dweller.stimpack = 2
    dweller.radaway = 1
    dweller.happiness = 75
    dweller.strength = 6
    dweller.perception = 5
    dweller.endurance = 4
    dweller.charisma = 7
    dweller.intelligence = 5
    dweller.agility = 6
    dweller.luck = 4
    return dweller


def _output(**action_fields: object) -> DwellerChatOutput:
    """Build a well-typed chat output and override its action fields as needed."""
    fields = {
        "response_text": "Ready when you are, Overseer.",
        "sentiment_score": 1,
        "reason_text": "The dweller is optimistic.",
        "action_type": "no_action",
        "action_reason": "No action needed.",
    }
    fields.update(action_fields)
    return DwellerChatOutput(**fields)


def test_stateless_agents_use_instructions_not_system_prompts() -> None:
    """Instructions avoid retaining obsolete context when no message history is passed."""
    for agent in (dweller_chat_agent, backstory_agent, bio_extension_agent, visual_attributes_agent):
        assert agent._instructions
        assert agent._system_prompts == ()
        assert agent._system_prompt_functions == []


def test_assignment_requires_complete_room_data() -> None:
    """An assignment cannot reach gameplay handling without an ID and display name."""
    output = _output(action_type="assign_to_room", action_room_id=uuid4())

    with pytest.raises(ModelRetry, match="action_room_name"):
        validate_dweller_chat_output(output)


def test_no_action_rejects_gameplay_payload() -> None:
    """No-action output may explain itself but cannot carry an executable action field."""
    output = _output(action_room_id=uuid4())

    with pytest.raises(ModelRetry, match="no_action must not include: action_room_id"):
        validate_dweller_chat_output(output)


def test_exploration_accepts_its_optional_supply_payload() -> None:
    """Existing server defaults remain valid when the model omits exploration supplies."""
    output = _output(action_type="start_exploration", action_duration_hours=6, action_stimpaks=2, action_radaways=1)

    assert validate_dweller_chat_output(output) is output


@pytest.mark.asyncio
async def test_test_model_records_usage_for_valid_structured_chat_output() -> None:
    """A deterministic model proves instructions, output parsing, and usage recording without a provider call."""
    deps = DwellerChatDeps(db_session=MagicMock(), dweller=_make_dweller(), vault_id=uuid4())
    model = TestModel(
        call_tools=[],
        custom_output_args={
            "response_text": "Ready when you are, Overseer.",
            "sentiment_score": 1,
            "reason_text": "The dweller is optimistic.",
            "action_type": "no_action",
            "action_reason": "No action needed.",
        },
    )

    with dweller_chat_agent.override(model=model):
        result = await dweller_chat_agent.run("How are you?", deps=deps)

    assert result.output.action_type == "no_action"
    assert result.usage.requests == 1
    assert result.usage.total_tokens > 0


@pytest.mark.asyncio
async def test_test_model_invokes_selected_room_recommendation_tool() -> None:
    """A deterministic model can exercise the chat agent's registered decision tools."""
    deps = DwellerChatDeps(db_session=MagicMock(), dweller=_make_dweller(), vault_id=uuid4())
    model = TestModel(
        call_tools=["get_best_room_recommendation"],
        custom_output_args={
            "response_text": "I am ready to help.",
            "sentiment_score": 1,
            "reason_text": "The dweller wants to contribute.",
            "action_type": "no_action",
            "action_reason": "No action needed.",
        },
    )

    with dweller_chat_agent.override(model=model):
        result = await dweller_chat_agent.run("Where would I be useful?", deps=deps)

    assert result.usage.tool_calls == 1


@pytest.mark.asyncio
async def test_test_model_invokes_activity_briefing_before_activity_suggestion() -> None:
    """The model can query grounded training/exploration state without a provider or database."""
    deps = DwellerChatDeps(db_session=MagicMock(), dweller=_make_dweller(), vault_id=uuid4())
    model = TestModel(
        call_tools=["get_dweller_activity_briefing"],
        custom_output_args={
            "response_text": "I am ready to improve, Overseer.",
            "sentiment_score": 1,
            "reason_text": "The dweller wants a productive activity.",
            "action_type": "no_action",
            "action_reason": "Awaiting a grounded activity recommendation.",
        },
    )
    briefing = DwellerActivityBriefing(
        exploration_active=False,
        available_stimpaks=2,
        available_radaways=1,
        recommended_exploration_duration_hours=4,
        recommended_stimpaks=2,
        recommended_radaways=1,
    )

    with (
        patch(
            "app.agents.dweller_chat_agent.build_dweller_activity_briefing",
            new_callable=AsyncMock,
            return_value=briefing,
        ) as mock_briefing,
        dweller_chat_agent.override(model=model),
    ):
        result = await dweller_chat_agent.run("Can I train or explore?", deps=deps)

    mock_briefing.assert_awaited_once_with(deps)
    assert result.usage.tool_calls == 1


@pytest.mark.asyncio
async def test_test_model_invokes_social_context_for_family_questions() -> None:
    """The chat agent can ground status and family answers in current vault data."""
    deps = DwellerChatDeps(db_session=MagicMock(), dweller=_make_dweller(), vault_id=uuid4())
    context = {
        "status": "Socializing",
        "room_name": "Living Room",
        "family": [{"name": "Sarah Jones", "relation": "partner"}],
        "relationships": [{"name": "Sarah Jones", "relationship_type": "partner", "affinity": 80}],
    }
    model = TestModel(
        call_tools=["get_dweller_social_context"],
        custom_output_args={
            "response_text": "Sarah and I are enjoying some time together.",
            "sentiment_score": 2,
            "reason_text": "The dweller is content.",
            "action_type": "no_action",
            "action_reason": "No action needed.",
        },
    )

    with (
        patch(
            "app.agents.dweller_chat_agent.build_dweller_social_context",
            new_callable=AsyncMock,
            return_value=context,
        ) as mock_context,
        dweller_chat_agent.override(model=model),
    ):
        result = await dweller_chat_agent.run("Who is my family, and what am I doing?", deps=deps)

    mock_context.assert_awaited_once_with(deps)
    assert result.usage.tool_calls == 1


@pytest.mark.asyncio
async def test_social_context_reports_live_status_family_and_affinity() -> None:
    dweller_id, partner_id, child_id = uuid4(), uuid4(), uuid4()
    dweller = MagicMock(id=dweller_id, room_id=uuid4(), partner_id=partner_id, parent_1_id=None, parent_2_id=None)
    dweller.status = DwellerStatusEnum.RESTING
    partner = MagicMock(id=partner_id, first_name="Sarah", last_name="Jones", parent_1_id=None, parent_2_id=None)
    child = MagicMock(id=child_id, first_name="Jamie", last_name="Jones", parent_1_id=dweller_id, parent_2_id=None)
    relationship = MagicMock(
        dweller_1_id=dweller_id,
        dweller_2_id=partner_id,
        relationship_type=MagicMock(value="partner"),
        affinity=80,
    )
    room_result, relationships_result, relatives_result = MagicMock(), MagicMock(), MagicMock()
    room_result.scalar_one_or_none.return_value = "Living Room"
    relationships_result.scalars.return_value.all.return_value = [relationship]
    relatives_result.scalars.return_value.all.return_value = [partner, child]
    session = MagicMock(
        get=AsyncMock(return_value=dweller),
        execute=AsyncMock(side_effect=[room_result, relationships_result, relatives_result]),
    )

    context = await build_dweller_social_context(
        DwellerChatDeps(db_session=session, dweller=MagicMock(id=dweller_id), vault_id=uuid4())
    )

    assert context["status"] == "Socializing"
    assert context["room_name"] == "Living Room"
    assert context["family"] == [
        {"name": "Sarah Jones", "relation": "partner"},
        {"name": "Jamie Jones", "relation": "child"},
    ]
    assert context["relationships"] == [{"name": "Sarah Jones", "relationship_type": "partner", "affinity": 80}]


@pytest.mark.asyncio
async def test_activity_suggestion_is_rejected_when_fresh_state_conflicts() -> None:
    """A stale model suggestion cannot emit a start-exploration card after exploration begins."""
    dweller = _make_dweller()
    dweller.id = uuid4()
    dweller.vault_id = uuid4()
    output = _output(action_type="start_exploration", action_duration_hours=4)
    briefing = DwellerActivityBriefing(
        exploration_active=True,
        available_stimpaks=2,
        available_radaways=1,
        exploration_blocker="Already exploring; suggest recall instead of another expedition.",
    )

    with patch(
        "app.agents.dweller_chat_agent.build_dweller_activity_briefing",
        new_callable=AsyncMock,
        return_value=briefing,
    ):
        result = await parse_action_suggestion(output, MagicMock(), dweller)

    assert isinstance(result, NoAction)
    assert result.reason == briefing.exploration_blocker


@pytest.mark.asyncio
async def test_training_suggestion_requires_a_fresh_matching_training_option() -> None:
    """The server rejects a model-selected stat when no matching room remains available."""
    dweller = _make_dweller()
    dweller.id = uuid4()
    dweller.vault_id = uuid4()
    output = _output(action_type="start_training", action_stat=SPECIALEnum.STRENGTH)
    briefing = DwellerActivityBriefing(
        exploration_active=False,
        available_stimpaks=2,
        available_radaways=1,
        training_blocker="No available training room can improve this dweller right now.",
    )

    with patch(
        "app.agents.dweller_chat_agent.build_dweller_activity_briefing",
        new_callable=AsyncMock,
        return_value=briefing,
    ):
        result = await parse_action_suggestion(output, MagicMock(), dweller)

    assert isinstance(result, NoAction)
    assert result.reason == briefing.training_blocker


@pytest.mark.asyncio
async def test_invalid_structured_output_retries_before_failing() -> None:
    """An invalid action shape consumes the configured bounded output-retry budget."""
    deps = DwellerChatDeps(db_session=MagicMock(), dweller=_make_dweller(), vault_id=uuid4())
    model = TestModel(
        call_tools=[],
        custom_output_args={
            "response_text": "I'll stand by.",
            "sentiment_score": 0,
            "reason_text": "No immediate need.",
            "action_type": "no_action",
            "action_room_id": str(uuid4()),
        },
    )

    with (
        dweller_chat_agent.override(model=model),
        pytest.raises(UnexpectedModelBehavior, match="maximum output retries"),
    ):
        await dweller_chat_agent.run("Anything to do?", deps=deps)
