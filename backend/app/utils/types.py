"""SQLAlchemy types implementing the application's instant contract."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator

from app.utils.time import as_naive_utc, as_utc


class UTCDateTime(TypeDecorator[datetime]):
    """Persist one UTC instant and read it back aware on every backend.

    PostgreSQL maps to ``timestamptz``. SQLite has no timezone storage, so a naive
    value is written after conversion to UTC and UTC is re-attached on read.
    Only ORM bind/result values are normalized: assigning a naive datetime to an
    instance does not coerce it, so comparisons before flush still need ``as_utc``.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return as_naive_utc(value) if dialect.name == "sqlite" else as_utc(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
