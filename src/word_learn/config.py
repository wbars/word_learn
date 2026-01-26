"""Configuration management using environment variables."""
from enum import Enum
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings


class Language(str, Enum):
    """Supported languages."""
    EN = "en"
    NL = "nl"
    RU = "ru"

    @property
    def column_name(self) -> str:
        """Get database column name for this language."""
        return self.value


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Bot configuration
    bot_token: str

    # Database
    database_url: str

    # Language pair
    source_lang: Language = Language.EN
    target_lang: Language = Language.RU

    # Timezone
    tz: str = "Europe/Amsterdam"

    # Spaced repetition
    max_stage: int = 33
    daily_pool_min: int = 67
    daily_pool_max: int = 76
    practice_batch_size: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def timezone(self) -> ZoneInfo:
        """Get timezone object."""
        return ZoneInfo(self.tz)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
