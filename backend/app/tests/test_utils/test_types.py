from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import Column, Integer, MetaData, Table, create_engine, select
from sqlalchemy.engine import Engine

from app.utils.types import UTCDateTime


def _sample_table() -> tuple[Engine, Table]:
    metadata = MetaData()
    table = Table(
        "utc_type_sample",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("at", UTCDateTime, nullable=False),
    )
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    return engine, table


def test_aware_values_round_trip_as_utc():
    engine, table = _sample_table()

    with engine.begin() as connection:
        connection.execute(
            table.insert().values(id=1, at=datetime(2026, 1, 1, 14, 0, tzinfo=timezone(timedelta(hours=2))))
        )
        stored = connection.execute(select(table.c.at)).scalar_one()

    assert stored == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert stored.tzinfo is not None


def test_naive_values_are_interpreted_as_utc():
    engine, table = _sample_table()

    with engine.begin() as connection:
        connection.execute(table.insert().values(id=1, at=datetime(2026, 1, 1, 12, 0)))
        stored = connection.execute(select(table.c.at)).scalar_one()

    assert stored == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_range_bounds_convert_offsets_before_comparing():
    engine, table = _sample_table()
    stored = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    with engine.begin() as connection:
        connection.execute(table.insert().values(id=1, at=stored))
        excluded = connection.execute(
            select(table.c.at).where(table.c.at <= datetime(2026, 1, 1, 11, 30, tzinfo=timezone(timedelta(hours=2))))
        ).all()
        included = connection.execute(
            select(table.c.at).where(table.c.at <= datetime(2026, 1, 1, 14, 0, tzinfo=timezone(timedelta(hours=2))))
        ).all()

    assert excluded == []
    assert included == [(stored,)]
