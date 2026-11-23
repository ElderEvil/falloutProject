import pytest
from pydantic import ValidationError

from app.models.llm_interaction import LLMInteractionBase

BASE = {"parameters": "test", "response": "test response", "usage": "chat"}


def test_base_model_accepts_token_fields():
    data = LLMInteractionBase(**BASE, prompt_tokens=100, completion_tokens=50, total_tokens=150)
    assert ((data.prompt_tokens, data.completion_tokens), data.total_tokens) == ((100, 50), 150)


def test_token_fields_are_optional():
    data = LLMInteractionBase(**BASE)
    assert (data.prompt_tokens, data.completion_tokens, data.total_tokens) == (None, None, None)
    assert (data.provider, data.model, data.instructions_hash, data.instructions_snapshot) == (None, None, None, None)


def test_token_fields_reject_negative_values():
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        LLMInteractionBase(**BASE, prompt_tokens=-1)


def test_legacy_usage_field_exists():
    assert LLMInteractionBase(**{**BASE, "usage": "image_generation"}).usage == "image_generation"
