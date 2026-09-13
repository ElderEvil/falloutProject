"""Tests for the @optional() partial-update decorator."""

from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.utils.partial import optional


class _WidgetBase(SQLModel):
    name: str
    tags: list[dict[str, Any]] = Field(default_factory=list, sa_column=sa.Column(JSONB, nullable=False))


@optional()
class _WidgetUpdate(_WidgetBase):
    pass


def test_optional_allows_factory_backed_fields() -> None:
    """A default_factory field must not collide with the decorator's None default."""
    update = _WidgetUpdate()

    assert update.name is None
    assert update.tags is None


def test_optional_keeps_explicit_values() -> None:
    update = _WidgetUpdate(tags=[{"source": "template", "text": "Born in Megaton."}])

    assert update.tags == [{"source": "template", "text": "Born in Megaton."}]
