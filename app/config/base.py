from pydantic import BaseSettings, EmailStr  # noqa: F401


class Settings(BaseSettings):
    API_VERSION: str = "v1"
    API_V1_STR: str = f"/api/{API_VERSION}"
    PROJECT_NAME: str = "Fallout Shelter API"
    SQLALCHEMY_DATABASE_URI = "sqlite:///database.db"

    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    SECRET_KEY = "secret"  # noqa: S105

    # EMAIL_TEST_USER: EmailStr = "test@example.com"
    # FIRST_SUPERUSER: EmailStr
    # FIRST_SUPERUSER_PASSWORD: str
    # USERS_OPEN_REGISTRATION: bool = True


settings = Settings()
