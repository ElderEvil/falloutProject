"""Tests for LLMInteraction CRUD token estimation for usage-less providers."""

from datetime import datetime
from uuid import uuid4

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


async def test_usage_creation_leaves_commit_to_caller(async_session):
    from app.models.llm_interaction import LLMInteraction

    row = await llm_interaction_crud.create(
        async_session, LLMInteractionCreate(parameters="Hi", response="Hello", usage="chat", total_tokens=7)
    )
    row_id = row.id
    await async_session.rollback()
    assert await async_session.get(LLMInteraction, row_id) is None


class TestAggregates:
    async def _seed(self, async_session, user_id) -> None:
        for usage, prompt, completion, total in [
            ("chat_with_dweller", 10, 20, 30),
            ("chat_with_dweller", 5, 5, 10),
            ("generate_backstory", 1, 1, 2),
        ]:
            await llm_interaction_crud.create(
                async_session,
                LLMInteractionCreate(
                    parameters="p",
                    response="r",
                    usage=usage,
                    user_id=user_id,
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    total_tokens=total,
                ),
            )

    async def test_aggregate_tokens_sums_all_time(self, async_session) -> None:
        user_id = uuid4()
        await self._seed(async_session, user_id)

        assert await llm_interaction_crud.aggregate_tokens(async_session, user_id) == (16, 26, 42)

    async def test_aggregate_tokens_empty(self, async_session) -> None:
        assert await llm_interaction_crud.aggregate_tokens(async_session, uuid4()) == (0, 0, 0)

    async def test_aggregate_by_operation_orders_heaviest_first(self, async_session) -> None:
        user_id = uuid4()
        await self._seed(async_session, user_id)

        rows = await llm_interaction_crud.aggregate_by_operation(async_session, user_id)

        assert [(r[0], r[3], r[4]) for r in rows] == [
            ("chat_with_dweller", 40, 2),
            ("generate_backstory", 2, 1),
        ]

    async def test_aggregates_respect_since(self, async_session) -> None:
        user_id = uuid4()
        await self._seed(async_session, user_id)

        future = datetime(2999, 1, 1)
        assert await llm_interaction_crud.aggregate_tokens(async_session, user_id, future) == (0, 0, 0)
        assert await llm_interaction_crud.aggregate_by_operation(async_session, user_id, future) == []
