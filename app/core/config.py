"""Application configuration using Pydantic Settings.

Loads configuration from environment variables and .env file.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ============ Application Settings ============
    APP_NAME: str = "AiGo"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # ============ Server Settings ============
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1

    # ============ Security Settings ============
    SECRET_KEY: str = Field(
        default="your-super-secret-key-change-in-production",
        description="Secret key for JWT encoding",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="Access token expiration time in minutes",
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        description="Refresh token expiration time in days",
    )

    # ============ CORS Settings ============
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins",
    )

    # ============ Database Settings ============
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "aigo"
    POSTGRES_PASSWORD: str = "aigo_password"
    POSTGRES_DB: str = "aigo_db"

    @computed_field  # type: ignore[misc]
    @property
    def DATABASE_URL(self) -> PostgresDsn:
        """Construct PostgreSQL async connection URL."""
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    @property
    def database_url(self) -> str:
        """Get database URL as string for Alembic."""
        return str(self.DATABASE_URL)

    # ============ Redis Settings ============
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_DB: int = 0
    REDIS_MAX_CONNECTIONS: int = 10
    REDIS_DEFAULT_TTL: int = 3600  # 1 hour

    @computed_field  # type: ignore[misc]
    @property
    def REDIS_URL(self) -> RedisDsn:
        """Construct Redis connection URL."""
        if self.REDIS_PASSWORD:
            return RedisDsn.build(
                scheme="redis",
                password=self.REDIS_PASSWORD,
                host=self.REDIS_HOST,
                port=self.REDIS_PORT,
                path=str(self.REDIS_DB),
            )
        return RedisDsn.build(
            scheme="redis",
            host=self.REDIS_HOST,
            port=self.REDIS_PORT,
            path=str(self.REDIS_DB),
        )

    # ============ Celery Settings ============
    CELERY_BROKER_DB: int = 1
    CELERY_RESULT_DB: int = 2

    @computed_field  # type: ignore[misc]
    @property
    def CELERY_BROKER_URL(self) -> str:
        """Construct Celery broker URL (Redis)."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.CELERY_BROKER_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.CELERY_BROKER_DB}"

    @computed_field  # type: ignore[misc]
    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        """Construct Celery result backend URL (Redis)."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.CELERY_RESULT_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.CELERY_RESULT_DB}"

    # ============ Amadeus API Settings ============
    AMADEUS_CLIENT_ID: str = Field(
        default="",
        description="Amadeus API Client ID",
    )
    AMADEUS_CLIENT_SECRET: str = Field(
        default="",
        description="Amadeus API Client Secret",
    )
    AMADEUS_BASE_URL: str = Field(
        default="https://test.api.amadeus.com",
        description="Amadeus API Base URL (use production URL in prod)",
    )

    # ============ Google Maps API Settings ============
    GOOGLE_MAPS_API_KEY: str = Field(
        default="",
        description="Google Maps API Key",
    )
    GOOGLE_PLACES_API_KEY: str = Field(
        default="",
        description="Google Places API Key (can be same as Maps)",
    )

    # ============ OpenAI Settings (for AI features) ============
    OPENAI_API_KEY: str = Field(
        default="",
        description="OpenAI API Key for AI-powered features",
    )
    OPENAI_MODEL: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model to use",
    )

    # ============ Weather API Settings ============
    WEATHER_API_KEY: str = Field(
        default="",
        description="Weather API Key (OpenWeatherMap or similar)",
    )
    WEATHER_API_BASE_URL: str = Field(
        default="https://api.openweathermap.org/data/2.5",
        description="Weather API Base URL",
    )

    # ============ Travelpayouts API Settings ============
    TRAVELPAYOUTS_TOKEN: str = Field(
        default="",
        description="Travelpayouts API Token for affiliate links",
    )
    TRAVELPAYOUTS_MARKER: str = Field(
        default="",
        description="Travelpayouts Marker ID for tracking",
    )
    TRAVELPAYOUTS_BASE_URL: str = Field(
        default="https://api.travelpayouts.com",
        description="Travelpayouts API Base URL",
    )

    # ============ Logging Settings ============
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # ============ OAuth Settings ============
    # Google OAuth
    GOOGLE_CLIENT_ID: str = Field(
        default="",
        description="Google OAuth Client ID",
    )
    GOOGLE_CLIENT_SECRET: str = Field(
        default="",
        description="Google OAuth Client Secret",
    )

    # Facebook OAuth
    FACEBOOK_APP_ID: str = Field(
        default="",
        description="Facebook App ID",
    )
    FACEBOOK_APP_SECRET: str = Field(
        default="",
        description="Facebook App Secret",
    )

    # Apple OAuth
    APPLE_CLIENT_ID: str = Field(
        default="",
        description="Apple Client ID (Service ID)",
    )
    APPLE_TEAM_ID: str = Field(
        default="",
        description="Apple Team ID",
    )
    APPLE_KEY_ID: str = Field(
        default="",
        description="Apple Key ID",
    )
    APPLE_PRIVATE_KEY: str = Field(
        default="",
        description="Apple Private Key (PEM format)",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
