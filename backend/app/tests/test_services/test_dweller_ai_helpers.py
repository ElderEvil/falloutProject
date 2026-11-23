"""Guard tests for the dweller AI helpers, plus the fake-agent doubles every dweller-AI test module shares."""

import contextlib
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.dweller import Dweller
from app.services.dweller_ai_service import _require_image_bytes, _resolve_dweller, dweller_ai
from app.services.quota_service import QuotaCheckResult
from app.utils.exceptions import AIProviderException, ValidationException

SVC = "app.services.dweller_ai_service"


STATS = {"strength": 5, "perception": 5, "endurance": 5, "charisma": 5, "intelligence": 5, "agility": 5, "luck": 5}
IDENTITY = {
    "first_name": "Test",
    "last_name": "Dweller",
    "gender": "male",
    "image_url": None,
    "visual_attributes": None,
    "rarity": "common",
    "weapon": None,
    "outfit": None,
}


def make_dweller(bio: str | None = None, **overrides) -> MagicMock:
    dweller = MagicMock(spec=Dweller, bio=bio, **IDENTITY, **STATS)
    dweller.configure_mock(**overrides)
    dweller.id = overrides.get("id") or uuid.uuid4()
    dweller.vault_id = uuid.uuid4()
    return dweller


def make_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    return user


def fake_db() -> MagicMock:
    return MagicMock(commit=AsyncMock())


def agent_result(output, *, input_tokens: int = 50, output_tokens: int = 30, total_tokens: int = 80) -> MagicMock:
    result = MagicMock()
    result.output = output
    result.usage.return_value = MagicMock(
        input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens
    )
    return result


@contextlib.contextmanager
def ai_env(
    agent: str | None = None,
    output=None,
    *,
    agents: dict[str, object] | None = None,
    usage: dict | None = None,
    storage=None,
    ai=None,
):
    """Patch the service's module-level collaborators; the doubles hang off the yielded namespace."""
    with contextlib.ExitStack() as stack:

        def collaborator(name) -> MagicMock:
            target = MagicMock()
            stack.enter_context(patch(f"{SVC}.{name}", target))
            return target

        doubles = SimpleNamespace(
            quota=collaborator("quota_service"),
            crud=collaborator("dweller_crud"),
            llm=collaborator("llm_interaction_crud"),
            map=collaborator("map_service"),
        )
        doubles.quota.check_quota = AsyncMock(
            return_value=QuotaCheckResult(
                allowed=True, remaining=500_000, limit=500_000, percentage=0.0, warning=False, used=0
            )
        )
        doubles.crud.update = AsyncMock()
        doubles.crud.get_full_info = AsyncMock()
        doubles.llm.create = AsyncMock()
        doubles.map.register_bio_places = AsyncMock()
        doubles.map.notify_bio_registration_failure = AsyncMock()
        if agent:
            doubles.agent = collaborator(agent)
            doubles.agent.run = AsyncMock(return_value=agent_result(output, **(usage or {})))
        for name, agent_output in (agents or {}).items():
            patched = collaborator(name)
            patched.run = AsyncMock(return_value=agent_result(agent_output))
            setattr(doubles, name, patched)
        if storage is not None:
            doubles.storage = storage
            stack.enter_context(patch.object(dweller_ai, "storage_service", storage))
        if ai is not None:
            doubles.ai = ai
            stack.enter_context(patch.object(dweller_ai, "ai_service", ai))
        yield doubles


async def test_resolve_dweller_prefers_the_supplied_dweller() -> None:
    supplied = MagicMock()
    assert await _resolve_dweller(MagicMock(), supplied, None) is supplied


async def test_resolve_dweller_loads_by_id() -> None:
    loaded = MagicMock()
    dweller_id = uuid.uuid4()
    with patch(f"{SVC}.dweller_crud.get_full_info", new_callable=AsyncMock, return_value=loaded) as get_full_info:
        resolved = await _resolve_dweller(MagicMock(), None, dweller_id)
    assert resolved is loaded
    get_full_info.assert_awaited_once()
    assert get_full_info.await_args.args[1] == dweller_id


async def test_resolve_dweller_without_an_identifier_fails_fast() -> None:
    with pytest.raises(ValidationException):
        await _resolve_dweller(MagicMock(), None, None)


def test_require_image_bytes_rejects_a_url() -> None:
    with pytest.raises(AIProviderException):
        _require_image_bytes("https://example.test/dweller.png")


def test_require_image_bytes_passes_image_data_through() -> None:
    payload = b"png-bytes"
    assert _require_image_bytes(payload) is payload
