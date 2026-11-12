from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./costumes.db"
    jwt_secret: str = "development-secret-change-me"
    app_url: str = "http://localhost:8000"
    upload_dir: Path = Path("uploads")
    jwt_expire_minutes: int = 60 * 24
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
