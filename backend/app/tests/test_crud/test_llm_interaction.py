"""Tests for LLMInteraction CRUD token estimation for usage-less providers."""

import pytest

from app.crud.llm_interaction import estimate_token_count
from app.crud.llm_interaction import llm_interaction as llm_interaction_crud
from app.schemas.llm_interaction import LLMInteractionCreate

pytestmark = pytest.mark.asyncio


class TestLLMInteractionTokenEstimation:
    async def test_estimates_tokens_when_provider_reports_none(self, async_session) -> None:
        obj = LLMInteractionCreate(
            parameters="Hello world",
            response="Hi there",
            usage="chat_with_dweller",
        )
        result = await llm_interaction_crud.create(async_session, obj)
        assert result.prompt_tokens == estimate_token_count("Hello world")
        assert result.completion_tokens == estimate_token_count("Hi there")
        assert result.total_tokens == result.prompt_tokens + result.completion_tokens

    async def test_preserves_reported_usage(self, async_session) -> None:
        obj = LLMInteractionCreate(
            parameters="Hi",
            response="Hello",
            usage="chat_with_dweller",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )
        result = await llm_interaction_crud.create(async_session, obj)
        assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (10, 5, 15)

    async def test_empty_text_estimates_at_least_one(self, async_session) -> None:
        obj = LLMInteractionCreate(parameters="", response="", usage="chat_with_dweller")
        result = await llm_interaction_crud.create(async_session, obj)
        assert result.prompt_tokens == 1
        assert result.completion_tokens == 1
        assert result.total_tokens == 2

    async def test_partial_usage_fills_missing_only(self, async_session) -> None:
        obj = LLMInteractionCreate(
            parameters="Some prompt text here",
            response="Short reply",
            usage="chat_with_dweller",
            prompt_tokens=10,
        )
        result = await llm_interaction_crud.create(async_session, obj)
        assert result.prompt_tokens == 10
        assert result.completion_tokens == estimate_token_count("Short reply")
        assert result.total_tokens == 10 + result.completion_tokens

    async def test_reported_total_preserves_estimated_components(self, async_session) -> None:
        obj = LLMInteractionCreate(
            parameters="Some long prompt text for estimation",
            response="A somewhat longer completion response here",
            usage="chat_with_dweller",
            total_tokens=99,
        )
        result = await llm_interaction_crud.create(async_session, obj)
        assert result.prompt_tokens == estimate_token_count("Some long prompt text for estimation")
        assert result.completion_tokens == estimate_token_count("A somewhat longer completion response here")
        assert result.total_tokens == 99
