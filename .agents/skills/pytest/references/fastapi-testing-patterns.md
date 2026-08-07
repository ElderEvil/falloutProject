# FastAPI Testing Patterns Reference

FastAPI-specific testing patterns and best practices.

## Dependency Overrides

### Basic Override

```python
from fastapi import FastAPI


app = FastAPI()


def get_db():
    # Production database dependency
    ...


def override_get_db():
    # Test database dependency
    ...


app.dependency_overrides[get_db] = override_get_db
```

### Override with Fixtures

```python
@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_session():
        yield db_session

    app.dependency_overrides[get_async_session] = override_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()  # ALWAYS clear after test
```

### Override Multiple Dependencies

```python
@pytest_asyncio.fixture
async def client_mocks(db_session: AsyncSession, mock_redis, mock_storage):
    app.dependency_overrides[get_async_session] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: mock_redis
    app.dependency_overrides[get_storage] = lambda: mock_storage

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()
```

### Per-Test Override

```python
async def test_admin_endpoint(async_client: AsyncClient):
    async def mock_admin():
        return User(id=1, is_superuser=True)

    app.dependency_overrides[get_current_user] = mock_admin
    try:
        response = await async_client.get("/admin/dashboard")
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
```

## Testing Different Endpoint Types

### Path Parameters

```python
async def test_get_item(async_client: AsyncClient):
    response = await async_client.get("/items/123")
    assert response.status_code == 200
```

### Query Parameters

```python
async def test_search_items(async_client: AsyncClient):
    response = await async_client.get("/items?q=stimpack&limit=10")
    assert response.status_code == 200
```

### Request Body

```python
async def test_create_item(async_client: AsyncClient):
    response = await async_client.post(
        "/items",
        json={"name": "Stimpack", "price": 25},
    )
    assert response.status_code == 201
```

### Form Data

```python
async def test_login(async_client: AsyncClient):
    response = await async_client.post(
        "/auth/login",
        data={"username": "test@example.com", "password": "secret"},
    )
    assert response.status_code == 200
```

### File Upload

```python
async def test_upload(async_client: AsyncClient):
    response = await async_client.post(
        "/upload",
        files={"file": ("photo.jpg", b"binary content", "image/jpeg")},
    )
    assert response.status_code == 200
```

## Testing Authentication

### Login Flow

```python
@pytest_asyncio.fixture
async def auth_client(db_session: AsyncSession):
    async def override_session():
        yield db_session

    app.dependency_overrides[get_async_session] = override_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Login
        response = await client.post(
            "/auth/login",
            data={"username": "test@example.com", "password": "secret"},
        )
        token = response.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"

        yield client

    app.dependency_overrides.clear()
```

### Testing Protected Endpoints

```python
async def test_protected_endpoint(auth_client: AsyncClient):
    response = await auth_client.get("/protected")
    assert response.status_code == 200


async def test_unprotected_endpoint(async_client: AsyncClient):
    response = await async_client.get("/public")
    assert response.status_code == 200
```

## Testing Background Tasks

```python
from fastapi import BackgroundTasks


async def test_background_task(async_client: AsyncClient):
    response = await async_client.post("/process")
    assert response.status_code == 202

    # Wait for background task to complete
    await asyncio.sleep(1)

    # Verify task completed
    response = await async_client.get("/status")
    assert response.json()["status"] == "completed"
```

## Testing WebSocket

```python
from fastapi.testclient import TestClient


def test_websocket():
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_text("hello")
        assert websocket.receive_text() == "hello"
```

## Testing Server-Sent Events

```python
async def test_sse(async_client: AsyncClient):
    async with async_client.stream("GET", "/events") as response:
        assert response.status_code == 200

        events = []
        async for line in response.aiter_text():
            if line.startswith("data: "):
                events.append(line[6:])

    assert len(events) > 0
```

## Testing Validation Errors

```python
async def test_validation_error(async_client: AsyncClient):
    # Missing required field
    response = await async_client.post("/items", json={})
    assert response.status_code == 422
    assert "field required" in str(response.json()["detail"])

    # Invalid type
    response = await async_client.post("/items", json={"price": "not-a-number"})
    assert response.status_code == 422
```

## Testing Error Responses

```python
async def test_not_found(async_client: AsyncClient):
    response = await async_client.get("/items/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Item not found"


async def test_forbidden(async_client: AsyncClient):
    response = await async_client.get("/admin")
    assert response.status_code == 403


async def test_conflict(async_client: AsyncClient):
    response = await async_client.post(
        "/items",
        json={"name": "Existing Item"},
    )
    assert response.status_code == 409
```

## Testing Pagination

```python
async def test_pagination(async_client: AsyncClient):
    response = await async_client.get("/items?page=1&size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 10
    assert data["total"] > 0
    assert data["page"] == 1
```

## Testing Filtering

```python
async def test_filtering(async_client: AsyncClient):
    response = await async_client.get(
        "/items",
        params={
            "status": "active",
            "min_price": 10,
            "max_price": 100,
        },
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert all(item["status"] == "active" for item in items)
```

## Testing Sorting

```python
async def test_sorting(async_client: AsyncClient):
    response = await async_client.get("/items?sort=name&order=asc")
    assert response.status_code == 200
    items = response.json()["items"]
    names = [item["name"] for item in items]
    assert names == sorted(names)
```

## Integration Test Pattern

```python
import pytest


@pytest.mark.integration
class TestUserWorkflow:
    """End-to-end user workflow tests."""

    async def test_register_login_protected(
        self, async_client: AsyncClient
    ):
        # Register
        response = await async_client.post(
            "/auth/register",
            json={
                "email": "new@example.com",
                "password": "secret123",
                "name": "New User",
            },
        )
        assert response.status_code == 201

        # Login
        response = await async_client.post(
            "/auth/login",
            data={"username": "new@example.com", "password": "secret123"},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]

        # Access protected endpoint
        response = await async_client.get(
            "/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["email"] == "new@example.com"
```

## Fixture Composition

```python
@pytest_asyncio.fixture
async def user(db_session: AsyncSession) -> User:
    user = User(
        email="test@example.com",
        name="Test User",
        hashed_password="hashed_secret",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def vault(db_session: AsyncSession, user: User) -> Vault:
    vault = Vault(name="Test Vault", owner_id=user.id)
    db_session.add(vault)
    await db_session.commit()
    return vault


@pytest_asyncio.fixture
async def populated_client(
    async_client: AsyncClient,
    user: User,
    vault: Vault,
) -> AsyncClient:
    # Pre-populate test data
    return async_client
```
