"""Shared pagination bounds; retain the existing query names and page defaults."""

from typing import Annotated

from pydantic import BaseModel, Field

PageLimit = Annotated[int, Field(ge=1, le=1000)]


class Pagination(BaseModel):
    """A page of rows; 1,000 supports complete-roster dashboard fetches."""

    skip: int = Field(0, ge=0)
    limit: PageLimit = 100


class OffsetPagination(Pagination):
    """Preserve the chat and notification APIs' public offset parameter."""

    skip: int = Field(0, alias="offset", ge=0)


class NotificationPagination(OffsetPagination):
    limit: PageLimit = 50


class PetPagination(Pagination):
    limit: int = Field(100, ge=1, le=100)
