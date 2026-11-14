"""Annotated datetime types that emit the canonical UTC ``Z`` wire format."""

from datetime import datetime
from typing import Annotated

from pydantic import PlainSerializer, WithJsonSchema

from app.utils.serialize import serialize_optional_utc_datetime, serialize_utc_datetime

# ``return_type=str`` leaves the serialization schema a bare string; restate the RFC 3339
# format so response schemas and generated clients keep the date-time annotation.
UTCDateTimeJSON = Annotated[
    datetime,
    PlainSerializer(serialize_utc_datetime, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "format": "date-time"}, mode="serialization"),
]
OptionalUTCDateTimeJSON = Annotated[
    datetime | None,
    PlainSerializer(serialize_optional_utc_datetime, return_type=str | None, when_used="json"),
]
