"""Deterministic contract tests for the stateless dweller Pydantic AI agents."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from uuid import uuid4

import pytest
from pydantic_ai.conversation import Conversation
from pydantic_ai.exceptions import ModelRetry, UsageLimitExceeded
from pydantic_ai.models.test import TestModel

from app.agents.chat_prompts import build_chat_instructions
from app.agents.dweller_agents import backstory_agent, bio_extension_agent, visual_attributes_agent
from app.agents.dweller_chat_agent import (
    CHAT_REQUEST_LIMIT,
    CHAT_TOOL_CALLS_LIMIT,
    CHAT_USAGE_LIMITS,
    DwellerActivityBriefing,
    DwellerChatDeps,
    DwellerChatOutput,
    build_dweller_social_context,
    dweller_chat_agent,
    parse_action_suggestion,
    usage_limits_for,
    validate_dweller_chat_output,
)
from app.core.enums import DwellerStatusEnum, SPECIALEnum
from app.schemas.chat import (
    BioAddendumAction,
    MedicalAidStatus,
    NoAction,
    RequestExitAction,
    RequestRadawayAction,
    RequestStimpakAction,
)
from app.services.medical_service import get_dweller_medical_status
from app.utils.exceptions import VaultOperationException


def _make_dweller() -> MagicMock:
    dweller = MagicMock(
        first_name="Casey",
        last_name="Jones",
        level=7,
        health=100,
        max_health=100,
        radiation=0,
        stimpack=2,
        radaway=1,
        happiness=75,
        strength=6,
        perception=5,
        endurance=4,
        charisma=7,
        intelligence=5,
        agility=6,
        luck=4,
        room=None,
        outfit=None,
        weapon=None,
        bio="Casey keeps the water purifier running and avoids unnecessary risks.",
    )
    dweller.gender.value, dweller.age_group.value, dweller.rarity.value = "female", "adult", "common"
    dweller.vault.number, dweller.vault.happiness = 13, 75
    dweller.vault.power = dweller.vault.power_max = 100
    dweller.vault.food = dweller.vault.food_max = 100
    dweller.vault.water = dweller.vault.water_max = 100
    # Property-backed so tests mutating max_health/radiation never read a stale cap.
    type(dweller).effective_max_health = PropertyMock(
        side_effect=lambda: max(1, dweller.max_health - dweller.radiation)
    )
    return dweller


def _live(**overrides: object) -> MagicMock:
    dweller = _make_dweller()
    dweller.id, dweller.vault_id = uuid4(), uuid4()
    for name, value in overrides.items():
        setattr(dweller, name, value)
    return dweller


def _output(**action_fields: object) -> DwellerChatOutput:
    fields = {
        "response_text": "Ready when you are, Overseer.",
        "sentiment_score": 1,
        "reason_text": "The dweller is optimistic.",
        "action_type": "no_action",
        "action_reason": "No action needed.",
    }
    fields.update(action_fields)
    return DwellerChatOutput(**fields)


def _medical_session(stimpack: int = 0, radaway: int = 0) -> MagicMock:
    storage_result = MagicMock()
    storage_result.scalar_one_or_none.return_value = MagicMock(stimpack=stimpack, radaway=radaway)
    return MagicMock(get=AsyncMock(return_value=None), execute=AsyncMock(return_value=storage_result))


def _family_free_session() -> MagicMock:
    family_result = MagicMock()
    family_result.scalars.return_value.all.return_value = []
    return MagicMock(get=AsyncMock(return_value=None), execute=AsyncMock(return_value=family_result))


def _deps(*, session: MagicMock | None = None, dweller: MagicMock | None = None) -> DwellerChatDeps:
    return DwellerChatDeps(
        db_session=session or _family_free_session(), dweller=dweller or _make_dweller(), vault_id=uuid4()
    )


def _model(*call_tools: str, **output: object) -> TestModel:
    defaults = {
        "response_text": "ok",
        "sentiment_score": 0,
        "reason_text": "neutral",
        "action_type": "no_action",
        "action_reason": "none",
    }
    return TestModel(call_tools=list(call_tools), custom_output_args=defaults | output)


BRIEFING = DwellerActivityBriefing(
    exploration_active=False,
    available_stimpaks=2,
    available_radaways=1,
    recommended_exploration_duration_hours=4,
    recommended_stimpaks=2,
    recommended_radaways=1,
)
SOCIAL_CONTEXT = {
    "status": "Socializing",
    "room_name": "Living Room",
    "family": [{"name": "Sarah Jones", "relation": "partner"}],
    "relationships": [{"name": "Sarah Jones", "relationship_type": "partner", "affinity": 80}],
}


def test_stateless_agents_use_instructions_not_system_prompts() -> None:
    for agent in (dweller_chat_agent, backstory_agent, bio_extension_agent, visual_attributes_agent):
        assert agent._instructions
        assert (agent._system_prompts, agent._system_prompt_functions) == ((), [])
    instructions = build_chat_instructions(_make_dweller())
    assert "irradiated water" in instructions
    assert "no armor stops that" in instructions


@pytest.mark.parametrize(
    ("action", "match"),
    [
        ({"action_type": "assign_to_room", "action_room_id": uuid4()}, "action_room_name"),
        ({"action_room_id": uuid4()}, "no_action must not include: action_room_id"),
        ({"action_type": "bio_addendum"}, "action_bio_text"),
        (
            {
                "action_type": "bio_addendum",
                "action_bio_text": "I keep a lucky wrench under my bunk.",
                "action_stat": SPECIALEnum.STRENGTH,
            },
            "must not include: action_stat",
        ),
    ],
)
def test_output_validation_rejects_malformed_actions(action: dict, match: str) -> None:
    with pytest.raises(ModelRetry, match=match):
        validate_dweller_chat_output(_output(**action))


@pytest.mark.parametrize(
    ("text", "expected"),
    [("I keep a lucky wrench under my bunk.", BioAddendumAction), (None, NoAction), ("short", NoAction)],
)
async def test_bio_addendum_requires_a_new_substantive_detail(text: str | None, expected: type) -> None:
    # None restates the recorded biography, which must not create a duplicate entry.
    dweller = _make_dweller()
    output = _output(action_type="bio_addendum", action_bio_text=dweller.bio if text is None else text)
    result = await parse_action_suggestion(output, _medical_session(), dweller)
    assert isinstance(result, expected)
    if expected is BioAddendumAction:
        assert result.bio_text == text


@pytest.mark.parametrize(
    ("error", "expected", "reason"),
    [
        (None, RequestExitAction, "I want to see the sky."),
        (VaultOperationException(detail="Only grown dwellers can leave"), NoAction, "Only grown dwellers can leave"),
    ],
)
async def test_request_exit_records_the_ask_or_downgrades(error: Exception | None, expected: type, reason: str) -> None:
    # Chatting about leaving records the ask; it must not end the chat's own transaction.
    service = MagicMock(request_exit=AsyncMock(side_effect=error) if error else AsyncMock())
    with patch("app.agents.chat_tools.exit_request_service", service):
        result = await parse_action_suggestion(
            _output(action_type="request_exit", action_reason="I want to see the sky."), _medical_session(), _live()
        )
    assert isinstance(result, expected)
    assert result.reason == reason
    if error is None:
        assert service.request_exit.await_args.kwargs["commit"] is False


async def test_test_model_invokes_selected_room_recommendation_tool() -> None:
    with dweller_chat_agent.override(model=_model("get_best_room_recommendation")):
        result = await dweller_chat_agent.run("Where would I be useful?", deps=_deps())
    assert result.usage.tool_calls == 1


@pytest.mark.parametrize(
    ("tool", "builder", "payload"),
    [
        ("get_dweller_activity_briefing", "build_dweller_activity_briefing", BRIEFING),
        ("get_dweller_social_context", "build_dweller_social_context", SOCIAL_CONTEXT),
    ],
)
async def test_test_model_invokes_context_tools(tool: str, builder: str, payload: object) -> None:
    deps = _deps()
    model = _model(tool)
    with (
        patch(f"app.agents.dweller_chat_agent.{builder}", new_callable=AsyncMock, return_value=payload) as mock_builder,
        dweller_chat_agent.override(model=model),
    ):
        result = await dweller_chat_agent.run("Who is my family, and what am I doing?", deps=deps)
    mock_builder.assert_awaited_once_with(deps)
    assert result.usage.tool_calls == 1
    if tool == "get_dweller_social_context":
        social_tool = next(
            t for t in model.last_model_request_parameters.function_tools if t.name == "get_dweller_social_context"
        )
        assert social_tool.parameters_json_schema["properties"]["topic"]["default"] == "general"


async def test_medical_status_tool_reports_thresholds_and_supplies() -> None:
    dweller = _make_dweller()
    dweller.health = 40
    dweller.radiation = 35  # effective max becomes 65
    session = _medical_session(stimpack=3, radaway=4)
    deps = DwellerChatDeps(db_session=session, dweller=dweller, vault_id=uuid4())
    status = await get_dweller_medical_status(deps.db_session, deps.dweller, deps.vault_id)
    assert isinstance(status, MedicalAidStatus)
    assert (
        (status.health_percent, status.radiation_percent),
        (status.available_stimpaks, status.available_radaways),
    ) == ((61.5, 35), (5, 5))
    assert status.recommended_action == "request_radaway"
    with dweller_chat_agent.override(
        model=_model(
            "get_dweller_medical_status",
            response_text="I need medical attention, Overseer.",
            sentiment_score=-1,
            reason_text="The dweller needs medical care.",
            action_type="request_stimpak",
            action_reason="Health is below 50%.",
        )
    ):
        result = await dweller_chat_agent.run("I feel weak.", deps=deps)
    assert result.usage.tool_calls == 1
    gated = await parse_action_suggestion(
        _output(action_type="request_stimpak", action_reason="Please help."),
        _medical_session(stimpack=1),
        _live(health=50),
    )
    assert isinstance(gated, NoAction)
    assert gated.reason == "Dweller does not currently need a Stimpak"


@pytest.mark.parametrize(
    ("race", "state", "health", "stimpack", "radiation", "action", "radaway", "expected"),
    [
        ("ghoul", "feral", 100, 0, 0, "request_exit", 0, NoAction),
        ("super_mutant", "behemoth", 100, 0, 0, "request_exit", 0, NoAction),
        ("ghoul", "feral", 20, 2, 0, "request_exit", 0, RequestStimpakAction),
        ("synth", "gen_1", 65, 0, 35, "request_radaway", 5, NoAction),
        ("synth", "gen_3", 65, 0, 35, "request_radaway", 5, RequestRadawayAction),
    ],
)
async def test_visual_attributes_gate_purposeful_actions(
    race: str, state: str, health: int, stimpack: int, radiation: int, action: str, radaway: int, expected: type
) -> None:
    dweller = _make_dweller()
    dweller.visual_attributes = {"race": race, "state_of_being": state}
    dweller.health, dweller.stimpack, dweller.radiation = health, stimpack, radiation
    result = await parse_action_suggestion(
        _output(action_type=action, action_reason="I want to leave."), _medical_session(radaway=radaway), dweller
    )
    assert isinstance(result, expected)


async def test_chat_agent_caps_runaway_tool_calls() -> None:
    # A valid no_action output keeps the validator happy, so only the tool-call limit can stop the loop.
    with (
        patch("app.agents.dweller_chat_agent.build_dweller_social_context", new_callable=AsyncMock, return_value={}),
        dweller_chat_agent.override(model=_model(*["get_dweller_social_context"] * 50)),
        pytest.raises(UsageLimitExceeded),
    ):
        await dweller_chat_agent.run("tell me about everyone", deps=_deps(), usage_limits=CHAT_USAGE_LIMITS)


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
    assert (context["status"], context["room_name"]) == ("Socializing", "Living Room")
    assert context["family"] == [
        {"name": "Sarah Jones", "relation": "partner"},
        {"name": "Jamie Jones", "relation": "child"},
    ]
    assert context["relationships"] == [{"name": "Sarah Jones", "relationship_type": "partner", "affinity": 80}]


@pytest.mark.parametrize(
    ("action", "blocker", "message"),
    [
        (
            {"action_type": "start_exploration", "action_duration_hours": 4},
            "exploration_blocker",
            "Already exploring; suggest recall instead of another expedition.",
        ),
        (
            {"action_type": "start_training", "action_stat": SPECIALEnum.STRENGTH},
            "training_blocker",
            "No available training room can improve this dweller right now.",
        ),
    ],
)
async def test_activity_suggestion_is_rejected_when_fresh_state_conflicts(
    action: dict, blocker: str, message: str
) -> None:
    briefing = DwellerActivityBriefing(
        exploration_active=blocker == "exploration_blocker",
        available_stimpaks=2,
        available_radaways=1,
        **{blocker: message},
    )
    with patch("app.agents.chat_tools.build_dweller_activity_briefing", new_callable=AsyncMock, return_value=briefing):
        result = await parse_action_suggestion(_output(**action), _medical_session(), _live())
    assert isinstance(result, NoAction)
    assert result.reason == message


def test_usage_limits_offset_by_carried_usage() -> None:
    conversation = Conversation()
    conversation.usage.requests = 40
    conversation.usage.tool_calls = 5
    limits = usage_limits_for(conversation)
    assert (limits.request_limit, limits.tool_calls_limit) == (40 + CHAT_REQUEST_LIMIT, 5 + CHAT_TOOL_CALLS_LIMIT)


def test_usage_limits_without_a_thread_are_the_exchange_caps() -> None:
    limits = usage_limits_for(None)
    assert (limits.request_limit, limits.tool_calls_limit) == (CHAT_REQUEST_LIMIT, CHAT_TOOL_CALLS_LIMIT)


async def test_a_thread_at_the_request_cap_can_still_talk() -> None:
    conversation = Conversation()
    conversation.usage.requests = CHAT_REQUEST_LIMIT
    with dweller_chat_agent.override(model=_model(response_text="still here.")):
        result = await dweller_chat_agent.run(
            "still there?", deps=_deps(), usage_limits=usage_limits_for(conversation), conversation=conversation
        )
    assert result.conversation.usage.requests == CHAT_REQUEST_LIMIT + 1
