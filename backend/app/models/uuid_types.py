"""UUID7 type definitions and utilities for time-sortable UUIDs.

This module provides UUID7 support using Python 3.14's native uuid.uuid7() function,
compatible with PostgreSQL 18's native uuidv7() function.
"""

from typing import TYPE_CHECKING, Annotated
from uuid import UUID
from uuid import uuid7 as _uuid7_gen

from pydantic_core import core_schema

if TYPE_CHECKING:
    from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
    from pydantic.json_schema import JsonSchemaValue


class UUID7(UUID):
    """UUID7 type with time-sortable properties.

    UUID7 provides:
    - Chronological sortability (time-ordered)
    - 48-bit timestamp (millisecond precision)
    - Monotonicity within same timestamp
    - Better database index performance vs UUID4

    Compatible with PostgreSQL 18's native uuidv7() function.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type,
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        """Pydantic core schema for UUID7 validation."""
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.uuid_schema(),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: core_schema.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        """JSON schema for UUID7 serialization."""
        return {"type": "string", "format": "uuid7"}

    @classmethod
    def _validate(cls, value: UUID | str | bytes) -> UUID:
        """Validate and convert input to UUID7.

        Args:
            value: UUID object, string, or bytes representation

        Returns:
            Valid UUID object

        Raises:
            ValueError: If value cannot be converted to valid UUID
        """
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            return UUID(value)
        if isinstance(value, bytes):
            return UUID(bytes=value)
        msg = f"Invalid UUID7: {value}"
        raise ValueError(msg)

    @property
    def timestamp_ms(self) -> int:
        """Extract millisecond timestamp from UUID7.

        Returns:
            Timestamp in milliseconds since Unix epoch
        """
        # UUID7 timestamp is in first 48 bits
        return (self.int >> 80) & 0xFFFFFFFFFFFF


def uuid7() -> UUID:
    """Generate a new UUID7 using Python 3.14's native implementation.

    Returns:
        UUID7 with current timestamp and random components

    Note:
        Uses Python 3.14's native uuid.uuid7() with 48-bit timestamp and 42-bit counter.
        Compatible with PostgreSQL 18's native uuidv7() function.
    """
    return _uuid7_gen()


# Type alias for use in Pydantic schemas
UUID7Type = Annotated[UUID, "UUID7 time-sortable identifier"]
