"""Application configuration.

Settings are loaded from environment variables (see .env.example).
This keeps configuration separated from application code and allows
the same code to run in different environments without modification.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] is the repository root.
_REPO_ROOT = Path(__file__).resolve().parents[3]


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

    # Step 5.8.25: after this many wrong passwords in a row for one username
    # from one client address, logins for that pair are refused for
    # LOGIN_LOCKOUT_MINUTES (see services/login_throttle.py).
    LOGIN_MAX_FAILED_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # Document storage - local filesystem for this prototype (see
    # docs/project_documentation/CUSTOMER_DOCUMENT_UPLOAD.md). Deliberately
    # isolated behind this one setting so it can be pointed at a different
    # mount, or swapped for S3/Azure/MinIO later, without touching the
    # documents table or any router/service code.
    DOCUMENT_STORAGE_ROOT: str = str(_REPO_ROOT / "infra" / "storage" / "documents")
    DOCUMENT_MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # Surveyor evidence storage - same local-filesystem-prototype approach
    # as document storage, kept as a separate root/setting (see
    # docs/project_documentation/SURVEYOR_DAMAGE_AND_EVIDENCE_WORKFLOW.md).
    EVIDENCE_STORAGE_ROOT: str = str(_REPO_ROOT / "infra" / "storage" / "evidence")
    EVIDENCE_MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # Step 5.8.12 document OCR - pytesseract is only a Python wrapper; the
    # Tesseract executable itself is a separate system-level install. Empty
    # string means "use whatever `tesseract` resolves to on PATH" (pytesseract's
    # own default) - set this only if Tesseract is installed somewhere PATH
    # does not cover. See docs/project_documentation/DOCUMENT_COMPLETENESS_AND_OCR.md.
    TESSERACT_CMD: str = ""

    # Step 5.4 risk-fusion research-prototype artifacts (read-only static
    # files, same source frontend/src/data/aiRiskFusionDemo.json was
    # hand-exported from - see docs/project_documentation/
    # AI_BACKEND_INTEGRATION.md). Never written to by the API.
    RISK_FUSION_ARTIFACTS_ROOT: str = str(_REPO_ROOT / "ai_ml" / "model_artifacts")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
