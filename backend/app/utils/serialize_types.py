"""Annotated datetime types that emit the canonical UTC ``Z`` wire format."""

from datetime import datetime
from typing import Annotated

from pydantic import PlainSerializer

from app.utils.serialize import serialize_optional_utc_datetime, serialize_utc_datetime

UTCDateTimeJSON = Annotated[datetime, PlainSerializer(serialize_utc_datetime, return_type=str, when_used="json")]
OptionalUTCDateTimeJSON = Annotated[
    datetime | None,
    PlainSerializer(serialize_optional_utc_datetime, return_type=str | None, when_used="json"),
]
