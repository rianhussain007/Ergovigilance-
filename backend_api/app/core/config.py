"""Application configuration — loads from environment variables with sensible defaults."""

import os
from typing import Literal


class Settings:
    APP_NAME: str = "ErgoVigilance API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost"
    ).split(",")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    USE_MOCK_REPOSITORY: bool = (
        os.getenv("USE_MOCK_REPOSITORY", "false").lower() == "true"
    )
    MOCK_DATA_DIR: str = os.getenv(
        "MOCK_DATA_DIR", "app/utils/mock_data"
    )
    AUTH_DB_PATH: str = os.getenv("AUTH_DB_PATH", "")


settings = Settings()
