"""
Centralized configuration using Pydantic Settings.
All environment variables are validated here.
"""

import logging
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # === API Configuration ===
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = True

    # === Database ===
    DATABASE_URL: str = "sqlite+aiosqlite:///./soar_lite.db"

    # === Logging ===
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # === API Keys (External Services) ===
    VIRUSTOTAL_API_KEY: str = ""
    ABUSEIPDB_API_KEY: str = ""

    def __init__(self, **data):
        """Initialize settings and ensure database path exists."""
        super().__init__(**data)
        self._ensure_sqlite_path()

    def _ensure_sqlite_path(self) -> None:
        """For SQLite, ensure parent directory exists."""
        if "sqlite" in self.DATABASE_URL:
            # Extract path from connection string: sqlite+aiosqlite:///./soar_lite.db
            db_path = self.DATABASE_URL.split("://")[-1]
            # Remove the first "/" if present
            if db_path.startswith("/"):
                db_path = db_path[1:]
            db_path = Path(db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)


# Singleton instance
settings = Settings()

# Configure logging based on settings
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)
logger.info(f"SOAR-Lite initialized with DATABASE_URL: {settings.DATABASE_URL}")
