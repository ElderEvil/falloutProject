from pydantic import EmailStr
from sqlmodel import SQLModel, Field


class UserBase(SQLModel):
    username: str = Field(..., index=True, min_length=3, max_length=32)
    email: EmailStr = Field(
        nullable=True,
        index=True,
        sa_column_kwargs={"unique": True},
    )
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str = Field(..., nullable=False)
