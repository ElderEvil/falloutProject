# httpx AsyncClient Reference

Comprehensive guide to httpx AsyncClient for testing FastAPI applications.

## Basic Setup

```python
from httpx import ASGITransport, AsyncClient


async def test_endpoint():
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
```

**Key points:**
- Always use `ASGITransport` for FastAPI (ASGI app)
- Use `base_url="http://test"` (any value works, required by httpx)
- Close client with `async with` or `await client.aclose()`

## HTTP Methods

```python
# GET
response = await client.get("/items")

# POST with JSON
response = await client.post("/items", json={"name": "Stimpack"})

# PUT
response = await client.put("/items/1", json={"name": "Updated"})

# PATCH
response = await client.patch("/items/1", json={"name": "Patched"})

# DELETE
response = await client.delete("/items/1")

# Custom method
response = await client.request("PURGE", "/cache")
```

## Request Bodies

### JSON

```python
response = await client.post(
    "/users",
    json={
        "email": "test@example.com",
        "name": "Test User",
    },
)
```

### Form Data

```python
response = await client.post(
    "/login",
    data={
        "username": "vault-user",
        "password": "secret",
    },
)
```

### File Upload

```python
from io import BytesIO


# Single file
response = await client.post(
    "/upload",
    files={
        "file": ("report.txt", BytesIO(b"content"), "text/plain"),
    },
)

# Multiple files
response = await client.post(
    "/upload",
    files=[
        ("files", ("file1.txt", b"content1", "text/plain")),
        ("files", ("file2.txt", b"content2", "text/plain")),
    ],
)

# File with form data
response = await client.post(
    "/upload",
    data={"description": "daily report"},
    files={"file": ("report.txt", b"content", "text/plain")},
)
```

## Authentication

### Bearer Token (Per-Request)

```python
headers = {"Authorization": "Bearer test-token"}
response = await client.get("/me", headers=headers)
```

### Bearer Token (Client-Wide)

```python
async with AsyncClient(
    transport=ASGITransport(app=app),
    base_url="http://test",
    headers={"Authorization": "Bearer test-token"},
) as client:
    response = await client.get("/me")
```

### Cookies

```python
# Per-request
response = await client.get("/profile", cookies={"session": "test-session"})

# Client-wide
async with AsyncClient(
    transport=ASGITransport(app=app),
    base_url="http://test",
    cookies={"session": "test-session"},
) as client:
    response = await client.get("/profile")
```

### Login Flow

```python
async def get_auth_headers(client: AsyncClient) -> dict:
    response = await client.post(
        "/auth/login",
        data={"username": "test@example.com", "password": "secret"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_protected_endpoint(async_client: AsyncClient):
    headers = await get_auth_headers(async_client)
    response = await async_client.get("/protected", headers=headers)
    assert response.status_code == 200
```

## Response Assertions

### Status Code

```python
assert response.status_code == 200
assert response.status_code == 201
assert response.status_code == 404
```

### JSON Content

```python
data = response.json()
assert data["name"] == "Stimpack"
assert data["id"] is not None
assert len(data["items"]) > 0
```

### Headers

```python
assert response.headers["content-type"] == "application/json"
assert "x-request-id" in response.headers
```

### Text Content

```python
assert response.text == "OK"
assert "error" in response.text.lower()
```

### Binary Content

```python
assert len(response.content) > 0
assert response.content.startswith(b"\x89PNG")
```

## Streaming Responses

```python
async def test_streaming(async_client: AsyncClient):
    async with async_client.stream("GET", "/events") as response:
        assert response.status_code == 200

        chunks = []
        async for chunk in response.aiter_text():
            chunks.append(chunk)

    assert "".join(chunks) == "event-1\nevent-2\n"
```

### Stream Iterators

```python
# By text
async for line in response.aiter_text():
    process(line)

# By bytes
async for chunk in response.aiter_bytes():
    process(chunk)

# By lines
async for line in response.aiter_lines():
    process(line)

# Raw
async for chunk in response.aiter_raw():
    process(chunk)
```

## Error Handling

### Testing 4xx/5xx Responses

```python
async def test_not_found(async_client: AsyncClient):
    response = await async_client.get("/items/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Item not found"
```

### Testing Validation Errors

```python
async def test_validation_error(async_client: AsyncClient):
    response = await async_client.post("/items", json={"name": ""})
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(e["field"] == "name" for e in errors)
```

### Testing Server Errors

```python
async def test_server_error(async_client: AsyncClient):
    response = await async_client.get("/broken-endpoint")
    assert response.status_code == 500
```

### Disable Exception Raising

```python
from httpx import ASGITransport, AsyncClient


transport = ASGITransport(
    app=app,
    raise_app_exceptions=False,  # Don't raise, return 500
)

async with AsyncClient(transport=transport, base_url="http://test") as client:
    response = await client.get("/broken")
    assert response.status_code == 500
```

## Lifespan Management

`ASGITransport` does NOT trigger lifespan events by default.

### Using asgi-lifespan

```python
from asgi_lifespan import LifespanManager


@pytest_asyncio.fixture
async def client_with_lifespan():
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://test",
        ) as client:
            yield client
```

### Manual Lifespan

```python
async def test_with_startup():
    async with LifespanManager(app):
        # App is started, startup events have run
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/health")
            assert response.status_code == 200
    # App is stopped, shutdown events have run
```

## Advanced Patterns

### Client with Custom Transport Options

```python
transport = ASGITransport(
    app=app,
    root_path="/api",           # For proxy testing
    client=("127.0.0.1", 12345),  # For client IP testing
)

async with AsyncClient(transport=transport, base_url="http://test") as client:
    response = await client.get("/whoami")
```

### Timeout Configuration

```python
from httpx import Timeout


async with AsyncClient(
    transport=ASGITransport(app=app),
    base_url="http://test",
    timeout=Timeout(30.0),  # 30 second timeout
) as client:
    response = await client.get("/slow-endpoint")
```

### Redirects

```python
# Follow redirects (default)
response = await client.get("/old-path")

# Don't follow redirects
response = await client.get("/old-path", follow_redirects=False)
assert response.status_code == 307
```

## Common Pitfalls

| Problem | Solution |
|---------|----------|
| `AsyncClient` not closed | Use `async with` context manager |
| Lifespan not triggered | Use `asgi-lifespan` `LifespanManager` |
| Connection pooling issues | Create client per test or per fixture |
| Timeout errors | Increase timeout or use `timeout=None` for tests |
| Deprecated `app=` shortcut | Use explicit `transport=ASGITransport(app=app)` |

## Integration with pytest-asyncio

```python
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    async def override_session():
        yield db_session

    app.dependency_overrides[get_async_session] = override_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()
```
