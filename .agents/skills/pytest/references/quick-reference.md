# Pytest Quick Reference Card

## Test Structure

```python
import pytest
from httpx import ASGITransport, AsyncClient


async def test_endpoint(async_client: AsyncClient):
    response = await async_client.get("/endpoint")
    assert response.status_code == 200
    assert response.json() == {"key": "value"}
```

## Fixture Hierarchy

```
engine (session)
  └── db_session (function)
        └── async_client (function)
              └── test_*(async_client)
```

## Common Assertions

```python
# Status
assert response.status_code == 200

# JSON
assert response.json()["key"] == "value"
assert "error" in response.json()

# Headers
assert response.headers["content-type"] == "application/json"

# Length
assert len(response.json()["items"]) == 10

# Contains
assert any(item["name"] == "Test" for item in response.json()["items"])
```

## HTTP Methods

```python
await client.get("/path")
await client.post("/path", json={})
await client.put("/path", json={})
await client.patch("/path", json={})
await client.delete("/path")
```

## Auth Headers

```python
headers = {"Authorization": f"Bearer {token}"}
response = await client.get("/protected", headers=headers)
```

## Override Dependencies

```python
app.dependency_overrides[get_db] = override_db
# ... test ...
app.dependency_overrides.clear()
```

## Run Tests

```bash
uv run pytest                          # All tests
uv run pytest -v                       # Verbose
uv run pytest -x                       # Stop on first failure
uv run pytest -k "test_name"           # By name
uv run pytest --tb=short               # Short traceback
uv run pytest --cov=app                # With coverage
```
