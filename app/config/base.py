from pydantic import BaseSettings, EmailStr


class Settings(BaseSettings):
    API_VERSION: str = "v1"
    API_V1_STR: str = f"/api/{API_VERSION}"
    PROJECT_NAME: str = "Fallout Shelter API"
    SQLALCHEMY_DATABASE_URI = "sqlite:///database.db"

    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    SECRET_KEY: str

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr = "felironman@gmail.com"
    FIRST_SUPERUSER_PASSWORD: str = "123456"
    USERS_OPEN_REGISTRATION: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
