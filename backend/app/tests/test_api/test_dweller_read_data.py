import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.asyncio
async def test_read_dweller_templates(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = await async_client.get("/dwellers/read_data/", headers=superuser_token_headers)

    assert response.status_code == 200
    templates = response.json()
    assert templates
    # Templates load with a typed visual_attributes model while the wire shape wants a
    # dict; a serialization mismatch here previously surfaced as a 500.
    for template in templates:
        visual_attributes = template["visual_attributes"]
        assert visual_attributes is None or isinstance(visual_attributes, dict)
