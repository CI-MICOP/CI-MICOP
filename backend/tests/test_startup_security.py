"""Step 5.8.26: production startup checks and API documentation access.

Items 5.4 and 5.5 of docs/project_documentation/SECURITY_AND_REGRESSION_REVIEW.md:
  A. Outside development the API refuses to start with a missing, default
     or weak JWT_SECRET_KEY.
  B. /docs, /redoc and /openapi.json are served in development only.

The "production" cases start the real app in a separate Python process with
ENVIRONMENT/JWT_SECRET_KEY set as environment variables (which take priority
over backend/.env), because the checks run when app.main is imported. Those
processes never open a database connection.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.config import (
    DEFAULT_JWT_SECRET_KEY,
    EXAMPLE_JWT_SECRET_KEY,
    MIN_JWT_SECRET_KEY_LENGTH,
    Settings,
    jwt_secret_key_problem,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
STRONG_SECRET = "s" * 24 + "-strong-test-secret-0123456789"

WEAK_SECRETS = [
    "",
    "   ",
    DEFAULT_JWT_SECRET_KEY,
    EXAMPLE_JWT_SECRET_KEY,
    "x" * (MIN_JWT_SECRET_KEY_LENGTH - 1),
]

_PROBE = """
import json
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
paths = ["/docs", "/redoc", "/openapi.json", "/api/v1/health", "/api/v1/auth/me"]
print(json.dumps({path: client.get(path).status_code for path in paths}))
"""


def _start_app(environment: str, secret: str | None) -> subprocess.CompletedProcess:
    env = {**os.environ, "ENVIRONMENT": environment}
    env.pop("JWT_SECRET_KEY", None)
    if secret is not None:
        env["JWT_SECRET_KEY"] = secret
    return subprocess.run(
        [sys.executable, "-c", _PROBE], cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=120
    )


def _settings(environment: str, secret: str) -> Settings:
    # _env_file=None: only the values given here, not backend/.env.
    return Settings(_env_file=None, ENVIRONMENT=environment, JWT_SECRET_KEY=secret)


# ============================================================== A: JWT secret


@pytest.mark.parametrize("secret", WEAK_SECRETS, ids=["empty", "blank", "default", "example", "short"])
def test_weak_secrets_are_reported(secret):
    assert jwt_secret_key_problem(secret) is not None


def test_strong_secret_is_accepted():
    assert jwt_secret_key_problem(STRONG_SECRET) is None


@pytest.mark.parametrize("secret", WEAK_SECRETS, ids=["empty", "blank", "default", "example", "short"])
@pytest.mark.parametrize("environment", ["production", "staging", "Production"])
def test_startup_check_refuses_weak_secret_outside_development(environment, secret):
    with pytest.raises(RuntimeError, match="Refusing to start"):
        _settings(environment, secret).check_startup_security()


def test_startup_check_error_does_not_echo_the_secret():
    secret = "short-but-private"
    with pytest.raises(RuntimeError) as error:
        _settings("production", secret).check_startup_security()
    assert secret not in str(error.value)


def test_missing_secret_falls_back_to_the_default_and_is_refused_in_production():
    settings = Settings(_env_file=None, ENVIRONMENT="production")
    assert settings.JWT_SECRET_KEY == DEFAULT_JWT_SECRET_KEY
    with pytest.raises(RuntimeError):
        settings.check_startup_security()


@pytest.mark.parametrize("environment", ["development", "test", "Development"])
def test_development_still_starts_with_the_default_secret(environment):
    _settings(environment, DEFAULT_JWT_SECRET_KEY).check_startup_security()


def test_production_with_a_strong_secret_passes_the_check():
    _settings("production", STRONG_SECRET).check_startup_security()


def test_real_app_refuses_to_start_in_production_with_the_default_secret():
    result = _start_app("production", DEFAULT_JWT_SECRET_KEY)
    assert result.returncode != 0
    assert "Refusing to start" in result.stderr


def test_real_app_refuses_to_start_in_production_without_a_secret(tmp_path):
    # Run from a folder with no .env, so JWT_SECRET_KEY is genuinely unset.
    env = {k: v for k, v in os.environ.items() if k != "JWT_SECRET_KEY"}
    env.update(ENVIRONMENT="production", PYTHONPATH=str(BACKEND_DIR))
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120
    )
    assert result.returncode != 0
    assert "JWT_SECRET_KEY" in result.stderr


# ============================================================== B: API docs


def test_docs_are_available_in_development(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_docs_are_closed_in_production_and_the_api_still_works():
    result = _start_app("production", STRONG_SECRET)
    assert result.returncode == 0, result.stderr
    status = json.loads(result.stdout.strip().splitlines()[-1])
    assert status["/docs"] == 404
    assert status["/redoc"] == 404
    assert status["/openapi.json"] == 404
    # Public and protected routes behave exactly as before.
    assert status["/api/v1/health"] == 200
    assert status["/api/v1/auth/me"] == 401
