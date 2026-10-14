"""Application configuration.

Settings are loaded from environment variables (see .env.example).
This keeps configuration separated from application code and allows
the same code to run in different environments without modification.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] is the repository root.
_REPO_ROOT = Path(__file__).resolve().parents[3]

# Step 5.8.26: ENVIRONMENT values that count as non-production. Any other
# value (e.g. "production", "staging", or a typo) is treated as production,
# so the startup checks and the closed API docs fail closed.
DEVELOPMENT_ENVIRONMENTS = frozenset({"development", "test"})

# The built-in fallback below and the placeholder in backend/.env.example -
# both publicly known, so neither may sign tokens in production.
DEFAULT_JWT_SECRET_KEY = "changeme"
EXAMPLE_JWT_SECRET_KEY = "<replace-with-a-strong-random-secret>"

# HS256 uses a 256-bit hash, so the key should be at least 32 bytes.
MIN_JWT_SECRET_KEY_LENGTH = 32


def jwt_secret_key_problem(secret: str | None) -> str | None:
    """Why `secret` is unsafe for signing tokens, or None if it is fine.
    The message never contains the secret itself."""
    value = (secret or "").strip()
    if not value:
        return "JWT_SECRET_KEY is missing or empty"
    if value in (DEFAULT_JWT_SECRET_KEY, EXAMPLE_JWT_SECRET_KEY):
        return "JWT_SECRET_KEY is still the publicly known default/example value"
    if len(value) < MIN_JWT_SECRET_KEY_LENGTH:
        return f"JWT_SECRET_KEY is shorter than {MIN_JWT_SECRET_KEY_LENGTH} characters"
    return None


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
    JWT_SECRET_KEY: str = DEFAULT_JWT_SECRET_KEY
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

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.strip().lower() in DEVELOPMENT_ENVIRONMENTS

    def check_startup_security(self) -> None:
        """Step 5.8.26: refuse to start outside development with a missing,
        default or weak JWT secret - anyone knowing it could sign valid
        tokens for any account. Development keeps working with the default."""
        if self.is_development:
            return
        problem = jwt_secret_key_problem(self.JWT_SECRET_KEY)
        if problem:
            raise RuntimeError(
                f"Refusing to start with ENVIRONMENT={self.ENVIRONMENT!r}: {problem}. "
                f"Set JWT_SECRET_KEY to a random value of at least {MIN_JWT_SECRET_KEY_LENGTH} characters."
            )


settings = Settings()
