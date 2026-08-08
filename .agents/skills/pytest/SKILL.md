---
name: pytest
description: Modern pytest patterns for FastAPI + async projects. Use when writing tests, configuring pytest, setting up async fixtures, testing endpoints, or debugging test failures. Covers pytest-asyncio, httpx AsyncClient, SQLModel/SQLAlchemy async testing, and dependency overrides.
---

# Modern Pytest for FastAPI + Async Projects

Comprehensive testing guide for FastAPI applications using pytest-asyncio, httpx AsyncClient, and async SQLModel/SQLAlchemy.

## When to Use This Skill

- Writing new tests for FastAPI endpoints
- Configuring pytest for async projects
- Setting up async database fixtures (SQLModel/SQLAlchemy)
- Testing with httpx AsyncClient
- Debugging async test failures
- Setting up test isolation and cleanup

## When NOT to Use This Skill

- Frontend testing (use `vitest` or `vue-testing-best-practices`)
- Non-async projects (use standard pytest patterns)
- Unit testing pure functions (standard pytest applies)

## Quick Reference

```bash
# Run tests
uv run pytest app/tests -v --tb=short

# Run with coverage
uv run pytest app/tests --cov=app --cov-report=term-missing

# Run specific test
uv run pytest app/tests/test_api/test_users.py::test_create_user -v

# Run by keyword
uv run pytest -k "test_login" -v
```

## Configuration (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
testpaths = ["app/tests"]
asyncio_mode = "auto"                          # No @pytest.mark.asyncio needed
asyncio_default_fixture_loop_scope = "session"  # Share event loop across session
pythonpath = ["."]
addopts = [
    "-ra",
    "--strict-markers",
    "--strict-config",
]
markers = [
    "integration: tests requiring database/redis or real service wiring",
]
filterwarnings = [
    "ignore::DeprecationWarning",
    "ignore::UserWarning",
]

[tool.coverage.run]
source = ["app"]
branch = true

[tool.coverage.report]
exclude_missing_lines = true
show_missing = true
```

**Key settings:**
- `asyncio_mode = "auto"` — async tests and fixtures work without decorators
- `asyncio_default_fixture_loop_scope = "session"` — one event loop per session (faster)
- Use `function` scope for maximum isolation (slower but safer)

## Fixture Architecture

### Layer 1: Session-Scoped Engine

```python
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine() -> AsyncEngine:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)

    yield engine

    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()
```

**Pool selection:**
| Pool | Use Case |
|------|----------|
| `StaticPool` | SQLite in-memory (shared across connections) |
| `NullPool` | Per-test PostgreSQL, event-loop isolation |
| Default async queue | Long-lived session-scoped PostgreSQL |

### Layer 2: Function-Scoped Session (Transaction Rollback)

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest_asyncio.fixture
async def db_session(engine: AsyncEngine) -> AsyncSession:
    async with engine.connect() as connection:
        transaction = await connection.begin()

        session_factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async with session_factory() as session:
            yield session

        await transaction.rollback()
```

**Why `join_transaction_mode="create_savepoint"`:**
- Application code can call `session.commit()` normally
- Test fixture rolls back the outer transaction after yield
- No need for manual event listeners

### Layer 3: HTTP Client with Dependency Override

```python
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncClient:
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()
```

## httpx AsyncClient Patterns

### Basic Request

```python
async def test_read_items(async_client: AsyncClient):
    response = await async_client.get("/items")
    assert response.status_code == 200
    assert response.json() == {"items": [...]}
```

### JSON Body

```python
async def test_create_item(async_client: AsyncClient):
    response = await async_client.post(
        "/items",
        json={"name": "Stimpack", "price": 25},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Stimpack"
```

### Authentication

```python
async def test_protected_endpoint(async_client: AsyncClient, auth_headers: dict):
    response = await async_client.get("/me", headers=auth_headers)
    assert response.status_code == 200


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient) -> dict:
    response = await async_client.post(
        "/auth/login",
        data={"username": "test@example.com", "password": "secret"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

### File Upload

```python
async def test_upload_file(async_client: AsyncClient):
    response = await async_client.post(
        "/upload",
        files={"file": ("report.txt", b"content", "text/plain")},
    )
    assert response.status_code == 200
```

### Streaming Response

```python
async def test_streaming(async_client: AsyncClient):
    async with async_client.stream("GET", "/events") as response:
        chunks = []
        async for chunk in response.aiter_text():
            chunks.append(chunk)
    assert "".join(chunks) == "event-1\nevent-2\n"
```

## WebSocket Testing

Use Starlette's `TestClient` for WebSocket testing (httpx doesn't support WebSockets):

```python
from fastapi.testclient import TestClient


def test_websocket():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_text("hello")
        assert ws.receive_text() == "hello"
```

## Dependency Overrides

### Override Single Dependency

```python
@pytest_asyncio.fixture
async def client_with_mock_db(db_session: AsyncSession):
    app.dependency_overrides[get_async_session] = lambda: db_session
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    app.dependency_overrides.clear()
```

### Override Multiple Dependencies

```python
@pytest_asyncio.fixture
async def client_mocks(db_session: AsyncSession, mock_redis):
    app.dependency_overrides[get_async_session] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: mock_redis
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    app.dependency_overrides.clear()
```

### Pattern: Override for Specific Tests

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

## Lifespan Testing

`ASGITransport` does NOT trigger lifespan events. Use `asgi-lifespan`:

```python
from asgi_lifespan import LifespanManager


@pytest_asyncio.fixture
async def client_with_lifespan(db_session: AsyncSession):
    async with LifespanManager(app) as manager:
        app.dependency_overrides[get_async_session] = lambda: db_session
        async with AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://test",
        ) as client:
            yield client
        app.dependency_overrides.clear()
```

## Test Isolation Patterns

### Per-Test Database Cleanup

```python
@pytest_asyncio.fixture
async def clean_db(engine: AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
```

### Transaction Rollback (Recommended)

```python
@pytest_asyncio.fixture
async def db_session(engine: AsyncEngine):
    async with engine.connect() as conn:
        txn = await conn.begin()
        async with AsyncSession(bind=conn, join_transaction_mode="create_savepoint") as session:
            yield session
        await txn.rollback()  # Undo all changes
```

## Common Pitfalls

| Problem | Solution |
|---------|----------|
| `RuntimeError: Task attached to a different loop` | Match resource lifetime to event loop scope; don't create async resources at module level |
| Async fixtures return coroutines | Use `@pytest_asyncio.fixture` (or `asyncio_mode = "auto"`) |
| Database state leaks between tests | Use transaction rollback isolation or `StaticPool` with in-memory SQLite |
| `ASGITransport` doesn't run lifespan | Wrap with `LifespanManager` from `asgi-lifespan` |
| Dependency overrides affect other tests | Always clear `app.dependency_overrides` in fixture teardown |
| `TestClient` fails inside `async def` | Use `httpx.AsyncClient` with `ASGITransport` instead |
| Tests hang intermittently | Enable `asyncio_debug = true` in pytest config |

## Debugging Async Tests

```toml
[tool.pytest.ini_options]
asyncio_debug = true  # Enable asyncio debug mode
```

Common debugging approach:

```python
import asyncio

async def test_concurrent_operations(async_client: AsyncClient):
    tasks = [
        async_client.get("/items/1"),
        async_client.get("/items/2"),
        async_client.get("/items/3"),
    ]
    responses = await asyncio.gather(*tasks)
    assert all(r.status_code == 200 for r in responses)
```

## Parallel Execution (pytest-xdist)

```bash
uv run pytest -n auto  # Run tests in parallel
```

**Important:** Each xdist worker is a separate process:
- Don't share in-memory databases between workers
- Use worker-specific database names: `f"test_db_{os.getenv('PYTEST_XDIST_WORKER', 'master')}"`
- Use `NullPool` for PostgreSQL to avoid cross-worker connection issues

## References

- [FastAPI Testing Guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [FastAPI Async Tests](https://fastapi.tiangolo.com/advanced/async-tests/)
- [SQLModel Testing](https://sqlmodel.tiangolo.com/tutorial/fastapi/tests/)
- [pytest-asyncio Docs](https://pytest-asyncio.readthedocs.io/)
- [httpx AsyncClient](https://www.python-httpx.org/async/)
