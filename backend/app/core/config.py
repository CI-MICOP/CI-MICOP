"""Application configuration.

Settings are loaded from environment variables (see .env.example).
This keeps configuration separated from application code and allows
the same code to run in different environments without modification.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # General
    PROJECT_NAME: str = "CI-MICOP API"
    ENVIRONMENT: str = "development"

    # API
    API_V1_PREFIX: str = "/api/v1"

    # CORS - origins allowed to call this API (comma-separated in .env)
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173"

    # Database (used by SQLAlchemy/Alembic once models are introduced)
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ci_micop"

    # Auth (used once authentication is implemented)
    JWT_SECRET_KEY: str = "changeme"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
