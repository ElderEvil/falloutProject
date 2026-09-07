# Async Database Testing Reference

Deep dive into async database testing with SQLModel/SQLAlchemy.

## Engine Configuration

### SQLite In-Memory (Fast Tests)

```python
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool


engine = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
```

**Why `StaticPool`:**
- Maintains single connection across all checkouts
- In-memory SQLite database stays alive
- All tests see the same data

### PostgreSQL (Production-Like)

```python
engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/test_db",
    poolclass=NullPool,  # Avoid cross-event-loop issues
)
```

**Why `NullPool`:**
- No connection reuse across event loops
- Each checkout creates fresh connection
- Avoids `Task attached to a different loop` errors

### File-Based SQLite (Isolation)

```python
import tempfile
from pathlib import Path


def create_file_engine(tmp_path: Path) -> AsyncEngine:
    return create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        poolclass=NullPool,
    )
```

## Session Management

### Basic Session Fixture

```python
@pytest_asyncio.fixture
async def db_session(engine: AsyncEngine) -> AsyncSession:
    async with async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )() as session:
        yield session
```

### Transaction Rollback Isolation

```python
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

**How it works:**
1. Opens connection and starts transaction
2. Creates session bound to that connection
3. Application code can call `session.commit()` (creates savepoints)
4. After yield, rolls back entire transaction
5. All changes are undone, no cleanup needed

### Savepoint Support

```python
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

When application code calls `session.commit()`:
- SQLAlchemy creates a savepoint
- Commit happens inside savepoint
- Outer transaction still rollbackable

## Table Creation

### Using `metadata.create_all()`

```python
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine():
    engine = create_async_engine("sqlite+aiosqlite://")

    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)

    yield engine

    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()
```

**Important:** Import all model modules before `create_all()`:

```python
# In conftest.py or test file
from app.models import User, Item, Vault  # Ensure tables are registered
```

### Using Alembic Migrations

```python
@pytest_asyncio.fixture(scope="session")
async def setup_database():
    # Run migrations against test database
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    yield
    # Cleanup if needed
```

## Query Patterns

### SQLModel Style

```python
async def test_user_query(db_session: AsyncSession):
    # Create
    user = User(name="Test", email="test@example.com")
    db_session.add(user)
    await db_session.commit()

    # Read
    result = await db_session.exec(select(User).where(User.name == "Test"))
    user = result.one()
    assert user.email == "test@example.com"
```

### SQLAlchemy Core Style

```python
async def test_user_query(db_session: AsyncSession):
    # Create
    await db_session.execute(insert(User).values(name="Test", email="test@example.com"))
    await db_session.commit()

    # Read
    result = await db_session.execute(select(User).where(User.name == "Test"))
    user = result.scalar_one()
    assert user.email == "test@example.com"
```

## Relationship Testing

### Eager Loading

```python
async def test_user_with_items(db_session: AsyncSession):
    # Avoid lazy loading in async context
    result = await db_session.execute(
        select(User).options(selectinload(User.items)).where(User.id == 1)
    )
    user = result.scalar_one()

    # Access relationship without additional query
    assert len(user.items) > 0
```

### Relationship Creation

```python
async def test_relationship(db_session: AsyncSession):
    user = User(name="Test")
    item = Item(name="Item", owner=user)

    db_session.add(user)
    await db_session.commit()

    # Verify both sides
    await db_session.refresh(user)
    await db_session.refresh(item)
    assert item.owner_id == user.id
    assert user.items[0].id == item.id
```

## JSON/JSONB Testing

### Basic Operations

```python
async def test_jsonb_operations(db_session: AsyncSession):
    doc = Document(payload={"status": "active", "count": 5})
    db_session.add(doc)
    await db_session.commit()

    # Containment query
    result = await db_session.execute(
        select(Document).where(Document.payload.contains({"status": "active"}))
    )
    assert result.scalar_one().id == doc.id
```

### Mutable Tracking

```python
from sqlalchemy.ext.mutable import MutableDict


class Document(SQLModel, table=True):
    payload: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB))


async def test_mutable_jsonb(db_session: AsyncSession):
    doc = Document(payload={"count": 0})
    db_session.add(doc)
    await db_session.commit()

    # In-place mutation (tracked by MutableDict)
    doc.payload["count"] = 1
    await db_session.commit()

    # Verify change persisted
    await db_session.refresh(doc)
    assert doc.payload["count"] == 1
```

## Enum Testing

### Python-to-DB Round Trip

```python
async def test_enum_round_trip(db_session: AsyncSession):
    item = Item(status=Status.ACTIVE)
    db_session.add(item)
    await db_session.commit()

    await db_session.refresh(item)
    assert item.status is Status.ACTIVE
```

### Invalid Values

```python
async def test_invalid_enum(db_session: AsyncSession):
    with pytest.raises((StatementError, DataError)):
        await db_session.execute(text("INSERT INTO item (status) VALUES ('invalid')"))
```

## PostgreSQL-Specific

### Schema Isolation

```python
import uuid


@pytest_asyncio.fixture
async def pg_session(postgres_engine: AsyncEngine):
    schema = f"test_{uuid.uuid4().hex}"

    async with postgres_engine.connect() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        await conn.execute(text(f'SET search_path TO "{schema}"'))
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.commit()

        transaction = await conn.begin()
        async with AsyncSession(bind=conn) as session:
            yield session
        await transaction.rollback()

        await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await conn.commit()
```

### Enum Inspection

```python
from sqlalchemy import inspect


async def test_pg_enum_labels(engine: AsyncEngine):
    def _check_status_enum(sync_conn) -> None:
        inspector = inspect(sync_conn)
        enums = inspector.get_enums()
        assert any(e["name"] == "status" for e in enums)

    async with engine.connect() as conn:
        await conn.run_sync(_check_status_enum)
```
