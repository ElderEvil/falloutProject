from pydantic import BaseModel


class InfoResponse(BaseModel):
    """Application information response schema."""

    app_version: str
    api_version: str
    environment: str
    python_version: str
    build_date: str


class ChangeEntry(BaseModel):
    """Individual change entry within a changelog version."""

    category: str
    description: str


class ChangelogEntry(BaseModel):
    """Changelog entry response schema."""

    version: str
    date: str
    date_display: str
    changes: list[ChangeEntry]
