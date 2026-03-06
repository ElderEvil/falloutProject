import pytest
from pydantic import ValidationError

from app.models.llm_interaction import LLMInteraction, LLMInteractionBase


class TestLLMInteractionModel:
    def test_base_model_accepts_token_fields(self):
        data = LLMInteractionBase(
            parameters="test",
            response="test response",
            usage="chat",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        assert data.prompt_tokens == 100
        assert data.completion_tokens == 50
        assert data.total_tokens == 150

    def test_token_fields_are_optional(self):
        data = LLMInteractionBase(
            parameters="test",
            response="test response",
            usage="chat",
        )
        assert data.prompt_tokens is None
        assert data.completion_tokens is None
        assert data.total_tokens is None

    def test_token_fields_reject_negative_values(self):
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            LLMInteractionBase(
                parameters="test",
                response="test response",
                usage="chat",
                prompt_tokens=-1,
            )

    def test_legacy_usage_field_exists(self):
        data = LLMInteractionBase(
            parameters="test",
            response="test response",
            usage="image_generation",
        )
        assert data.usage == "image_generation"
