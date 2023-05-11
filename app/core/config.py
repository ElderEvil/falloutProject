from typing import Any

from pydantic import BaseSettings, EmailStr, PostgresDsn, validator


class Settings(BaseSettings):
    API_VERSION: str = "v1"
    API_V1_STR: str = f"/api/{API_VERSION}"
    PROJECT_NAME: str = "Fallout Shelter API"

    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    SECRET_KEY: str = "09d25e0sas4faa6c52gf6c818166b7a9563b93f7sdsdef6f0f4caa6cf63b88e8d3e7"

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER_USERNAME: str = "ElderEvil"
    FIRST_SUPERUSER_EMAIL: EmailStr = "lordofelderevil@gmail.com"
    FIRST_SUPERUSER_PASSWORD: str = "pa$$word"
    USERS_OPEN_REGISTRATION: bool = True

    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    SQLALCHEMY_DATABASE_URI: PostgresDsn | None = None

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: str | None, values: dict[str, Any]) -> Any:  # noqa: N805
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql",
            user=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_SERVER"),
            path=f"/{values.get('POSTGRES_DB') or ''}",
        )

    class Config:
        env_file = ".env"


settings = Settings()
