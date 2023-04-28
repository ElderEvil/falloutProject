from pydantic import BaseSettings


class Settings(BaseSettings):
    API_VERSION: str = "v1"
    API_V1_STR: str = f"/api/{API_VERSION}"
    PROJECT_NAME: str = "Fallout Shelter API"
    SQLALCHEMY_DATABASE_URI = "sqlite:///database.db"


settings = Settings()
