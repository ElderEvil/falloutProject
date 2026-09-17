"""Guard tests for the dweller AI service's dweller-resolution and image helpers."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.dweller_ai import _require_image_bytes, _resolve_dweller
from app.utils.exceptions import AIProviderException, ValidationException


@pytest.mark.asyncio
async def test_resolve_dweller_prefers_the_supplied_dweller() -> None:
    """Callers that already hold the read model must not trigger a second query."""
    supplied = MagicMock()

    assert await _resolve_dweller(MagicMock(), supplied, None) is supplied


@pytest.mark.asyncio
async def test_resolve_dweller_loads_by_id() -> None:
    loaded = MagicMock()
    dweller_id = uuid4()

    with patch(
        "app.services.dweller_ai.dweller_crud.get_full_info", new_callable=AsyncMock, return_value=loaded
    ) as get_full_info:
        resolved = await _resolve_dweller(MagicMock(), None, dweller_id)

    assert resolved is loaded
    get_full_info.assert_awaited_once()
    assert get_full_info.await_args.args[1] == dweller_id


@pytest.mark.asyncio
async def test_resolve_dweller_without_an_identifier_fails_fast() -> None:
    """Neither an id nor a dweller means the caller passed nothing usable."""
    with pytest.raises(ValidationException):
        await _resolve_dweller(MagicMock(), None, None)


def test_require_image_bytes_rejects_a_url() -> None:
    """A URL response cannot be uploaded as file data."""
    with pytest.raises(AIProviderException):
        _require_image_bytes("https://example.test/dweller.png")


def test_require_image_bytes_passes_image_data_through() -> None:
    payload = b"png-bytes"

    assert _require_image_bytes(payload) is payload
