from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./data/ai_trends.db"
    data_dir: str = str(Path(__file__).parent.parent / "data")
    scan_interval_hours: int = 168  # weekly
    cors_origins: list[str] = ["*"]
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
