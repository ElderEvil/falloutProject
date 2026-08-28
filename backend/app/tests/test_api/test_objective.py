"""Objective endpoint authorization tests."""

from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_manual_objective_completion_requires_admin(async_client) -> None:
    """Players cannot invoke the manual completion tool."""
    response = await async_client.post(f"/objectives/{uuid4()}/{uuid4()}/complete")

    assert response.status_code == 401
