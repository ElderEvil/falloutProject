from pydantic import EmailStr
from sqlmodel import SQLModel, Field

from app.models.base import TimeStampMixin, BaseUUIDModel


class UserBase(SQLModel):
    username: str = Field(..., index=True, min_length=3, max_length=32, unique=True)
    email: EmailStr = Field(
        nullable=True,
        index=True,
        sa_column_kwargs={"unique": True},
    )
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)


class User(BaseUUIDModel, UserBase, TimeStampMixin, table=True):
    hashed_password: str = Field(..., nullable=False)
