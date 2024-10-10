from pathlib import Path

import typer

app = typer.Typer()


def create_file_with_boilerplate(file_path: Path, content: str):
    """Helper function to create a file with boilerplate code."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if not file_path.exists():
        file_path.write_text(content)
        typer.echo(f"Created {file_path}")
    else:
        typer.echo(f"{file_path} already exists, skipping creation.")


def append_to_file(file_path: Path, content: str):
    """Helper function to append content to a file."""
    with open(file_path, "a") as file:
        file.write(content)
    typer.echo(f"Appended to {file_path}")


@app.command()
def startapp(name: str):
    """Create a model, schema, CRUD, API, and service for the given name"""

    # Model
    model_content = f"""
from pydantic import BaseModel

from app.models.base import BaseUUIDModel, TimeStampMixin

class {name.capitalize()}Base(BaseModel):
    pass
    # Add fields here


class {name.capitalize()}(BaseUUIDModel, {name.capitalize()}Base, TimeStampMixin, table=True):
    pass

"""
    create_file_with_boilerplate(Path(f"app/models/{name.lower()}.py"), model_content)

    # Schema
    schema_content = f"""
from uuid import UUID


from app.models.{name.lower()} import {name.capitalize()}Base
from app.utils.partial import optional

class {name.capitalize()}Create({name.capitalize()}Base):
    pass

class {name.capitalize()}Read({name.capitalize()}Base):
    id: UUID

@optional()
class {name.capitalize()}Update({name.capitalize()}Base):
    pass

"""
    create_file_with_boilerplate(Path(f"app/schemas/{name.lower()}.py"), schema_content)

    # CRUD
    crud_content = f"""
from app.models.{name.lower()} import {name.capitalize()}
from app.crud.base import CRUDBase
from app.schemas.{name.lower()} import {name.capitalize()}Create, {name.capitalize()}Update

class CRUD{name.capitalize()}(CRUDBase[{name.capitalize()}, {name.capitalize()}Create, {name.capitalize()}Update]):
    pass

{name.lower()} = CRUD{name.capitalize()}({name.capitalize()})
"""
    create_file_with_boilerplate(Path(f"app/crud/{name.lower()}.py"), crud_content)

    # Append to crud/__init__.py
    crud_init_content = f"from .{name.lower()} import {name.lower()}\n"
    append_to_file(Path("app/crud/__init__.py"), crud_init_content)
    # API
    api_content = f"""
from typing import Annotated

from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.schemas.{name.lower()} import {name.capitalize()}Create, {name.capitalize()}Read
from app.models.{name.lower()} import {name.capitalize()}
from app import crud
from app.db.session import get_async_session


router = APIRouter()

@router.post("/", response_model={name.capitalize()}Read)
def create_{name.lower()}(
    {name.lower()}_data: {name.capitalize()}Create,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    return crud.{name.lower()}.create(db_session, {name.lower()}_data)
"""
    create_file_with_boilerplate(Path(f"app/api/v1/endpoints/{name.lower()}.py"), api_content)

    # Service
    service_content = f"""
def get_{name.lower()}_details():
    # Add logic to get details
    pass
"""
    create_file_with_boilerplate(Path(f"app/services/{name.lower()}.py"), service_content)

    typer.echo(f"All components for {name.capitalize()} created successfully!")


if __name__ == "__main__":
    app()
