from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuration settings for LinqAlpha Agent.

    All settings are loaded from environment variables or .env file.
    """

    # Required: LinqAlpha API Key for Search Chat
    linqalpha_api_key: str

    # Optional: RMS features configuration (required for RMS Chat and Deep Research)
    linqalpha_org_id: Optional[str] = None
    linqalpha_user_id: Optional[str] = None
    linqalpha_user_email: Optional[str] = None
    linqalpha_user_name: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
