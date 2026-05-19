---
name: sqlmodel
description: SQLModel best practices and conventions for FastAPI applications. Use when defining models, writing queries, managing sessions, or working with SQLAlchemy relationships. Covers patterns specific to SQLModel (not raw SQLAlchemy).
---

# SQLModel

This project uses **SQLModel** as its ORM layer on top of SQLAlchemy. SQLModel combines SQLAlchemy 2.0 with Pydantic v2 for unified model definitions.

## Model Definition Patterns

### Table Model (Full Model with DB + Pydantic)

```python
from sqlmodel import SQLModel, Field, Relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.relationship import RelatedModel


class Dweller(SQLModel, table=True):
    __tablename__ = "dwellers"

    id: UUID4 = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True, max_length=100)
    level: int = Field(default=1, ge=1, le=50)
    is_active: bool = Field(default=True)

    # Relationships use back-populates
    rooms: list["Room"] = Relationship(back_populates="dwellers", sa_relationship_kwargs={"lazy": "selectin"})
```

### Shared Model (Base for Request/Response without table)

```python
class DwellerBase(SQLModel):
    """Shared base for create/update schemas."""
    name: str = Field(max_length=100)
    level: int = Field(default=1, ge=1, le=50)


class DwellerCreate(DwellerBase):
    """Request schema for creating dwellers."""
    vault_id: UUID4


class DwellerRead(DwellerBase):
    """Response schema — excludes internal fields."""
    id: UUID4
    is_active: bool


class DwellerUpdate(DwellerBase):
    """Request schema for updates — all fields optional."""
    name: str | None = None
    level: int | None = None
```

### Field Types

- Use `UUID4` for primary keys: `Field(default_factory=uuid4, primary_key=True)`
- Use `Field(index=True)` for frequently queried columns
- Use `Field(max_length=N)` for string validation (generates VARCHAR)
- Use `Field(ge=N, le=M)` for numeric validation
- Use `Field(default=...)` for defaults; omit `default` for required fields
- Use `Field(sa_column=Column(...))` for custom SQLAlchemy column types

## Session Management

### Dependency Pattern (FastAPI)

```python
from collections.abc import Generator
from sqlmodel import Session
from app.core.database import engine


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
```

### Usage in Endpoints

```python
from fastapi import Depends
from sqlmodel import Session, select


@app.get("/dwellers/{dweller_id}")
def get_dweller(
    dweller_id: UUID4,
    session: Session = Depends(get_session),
) -> DwellerRead:
    dweller = session.get(Dweller, dweller_id)
    if not dweller:
        raise ResourceNotFoundException("Dweller not found")
    return DwellerRead.model_validate(dweller)
```

## Query Patterns

### Basic Queries

```python
from sqlmodel import select, col, func


# Get by ID
dweller = session.get(Dweller, dweller_id)

# Select with filter
statement = select(Dweller).where(Dweller.is_active == True)
dwellers = session.exec(statement).all()

# Select with multiple conditions
statement = select(Dweller).where(
    col(Dweller.level) >= 10,
    Dweller.vault_id == vault_id,
)
dwellers = session.exec(statement).all()

# First result
statement = select(Dweller).where(Dweller.name == "John")
dweller = session.exec(statement).first()

# Count
statement = select(func.count()).select_from(Dweller)
count = session.exec(statement).one()
```

### Pagination

```python
def get_dwellers(
    session: Session,
    offset: int = 0,
    limit: int = 20,
) -> list[Dweller]:
    statement = select(Dweller).offset(offset).limit(limit)
    return list(session.exec(statement).all())
```

### Relationships

```python
# Eager loading via sa_relationship_kwargs
class Vault(SQLModel, table=True):
    dwellers: list["Dweller"] = Relationship(
        back_populates="vault",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

# Accessing loaded relationship
vault = session.get(Vault, vault_id)
for dweller in vault.dwellers:  # No N+1, already loaded
    ...
```

## CRUD Patterns

### Create

```python
def create_dweller(session: Session, dweller_data: DwellerCreate) -> Dweller:
    dweller = Dweller.model_validate(dweller_data)
    session.add(dweller)
    session.commit()
    session.refresh(dweller)
    return dweller
```

### Update

```python
def update_dweller(
    session: Session,
    dweller: Dweller,
    dweller_data: DwellerUpdate,
) -> Dweller:
    update_data = dweller_data.model_dump(exclude_unset=True)
    dweller.sqlmodel_update(update_data)
    session.add(dweller)
    session.commit()
    session.refresh(dweller)
    return dweller
```

### Delete

```python
def delete_dweller(session: Session, dweller: Dweller) -> None:
    session.delete(dweller)
    session.commit()
```

## Alembic Migrations

SQLModel works with Alembic. Key patterns:

- `alembic revision --autogenerate -m "description"` generates migrations
- Review generated migrations before applying
- Use `alembic upgrade head` to apply
- For complex changes (type changes, renames), write manual migration steps

### Adding a New Model

1. Define the model in `backend/app/models/`
2. Run `uv run alembic revision --autogenerate -m "add_<model>_table"`
3. Review the generated migration file
4. Run `uv run alembic upgrade head`

## Type Hints

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.vault import Vault

class Dweller(SQLModel, table=True):
    # Forward reference for type checking only
    vault: "Vault" = Relationship(back_populates="dwellers")
```

## Common Pitfalls

- **DO NOT** mix SQLAlchemy 1.x patterns (`session.query()`) — use `select()` statements
- **DO NOT** use `session.add()` without `session.commit()` for persistence
- **DO NOT** forget `session.refresh()` after commit if you need DB-generated values
- **DO NOT** use `__init__` overrides on table models — use `model_validate()` or `model_construct()`
- **DO** use `exclude_unset=True` in update schemas to avoid nulling out unchanged fields
- **DO** use `sqlmodel_update()` for partial updates, not direct attribute assignment
- **DO** use `Relationship` for foreign keys, not raw `ForeignKey` + manual joins
- **DO** use `TYPE_CHECKING` blocks for circular model references

## Pydantic v2 Integration

SQLModel models are Pydantic models. All Pydantic v2 patterns apply:

- `model_validate()` — create from dict/ORM object
- `model_dump()` — convert to dict
- `model_dump(exclude_unset=True)` — only changed fields
- `model_json_schema()` — generate JSON schema
- Field validators via `field_validator()` decorator
- Model validators via `model_validator()` decorator
