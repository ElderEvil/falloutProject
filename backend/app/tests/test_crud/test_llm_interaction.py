"""Tests for LLMInteraction CRUD token estimation for usage-less providers."""

import pytest

from app.crud.llm_interaction import estimate_token_count
from app.crud.llm_interaction import llm_interaction as llm_interaction_crud
from app.schemas.llm_interaction import LLMInteractionCreate

pytestmark = pytest.mark.asyncio


class TestLLMInteractionTokenEstimation:
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
