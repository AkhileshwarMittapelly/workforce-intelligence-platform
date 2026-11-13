"""Application configuration and environment settings."""

import os
from functools import lru_cache
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Platform configuration settings loaded from environment variables."""

    # Database Credentials & Host
    db_host: str = os.getenv("DB_HOST") or os.getenv("MYSQL_HOST") or "localhost"
    db_port: int = int(os.getenv("DB_PORT") or os.getenv("MYSQL_PORT") or 3306)
    db_name: str = os.getenv("DB_NAME") or os.getenv("MYSQL_DATABASE") or "workforce_intelligence"
    db_user: str = os.getenv("DB_USER") or os.getenv("MYSQL_USER") or "root"
    db_password: str = os.getenv("DB_PASSWORD") or os.getenv("MYSQL_PWD") or os.getenv("MYSQL_PASSWORD") or ""
    db_pool_size: int = int(os.getenv("DB_POOL_SIZE") or 10)
    db_max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW") or 20)
    db_pool_recycle: int = int(os.getenv("DB_POOL_RECYCLE") or 3600)

    # Application
    app_env: str = os.getenv("APP_ENV") or "development"
    app_debug: bool = os.getenv("APP_DEBUG", "True").lower() in ("true", "1", "yes")
    app_title: str = os.getenv("APP_TITLE") or "Workforce Intelligence Platform"
    scenario_date: str = os.getenv("SCENARIO_DATE") or "2026-11-11"

    # Streamlit
    streamlit_server_port: int = int(os.getenv("STREAMLIT_SERVER_PORT") or 8501)
    streamlit_server_address: str = os.getenv("STREAMLIT_SERVER_ADDRESS") or "0.0.0.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """
        Constructs the SQLAlchemy connection URL for MySQL with PyMySQL driver.
        Handles URL-encoding of special characters in passwords.
        """
        encoded_password = quote_plus(self.db_password) if self.db_password else ""
        return (
            f"mysql+pymysql://{self.db_user}:{encoded_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


@lru_cache()
def get_settings() -> Settings:
    """Returns a cached instance of the settings."""
    return Settings()
