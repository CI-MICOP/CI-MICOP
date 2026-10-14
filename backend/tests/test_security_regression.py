"""Step 5.8.23: security regression tests (roadmap item 11).

Fills the gaps found by the security review - see
docs/project_documentation/SECURITY_AND_REGRESSION_REVIEW.md. Earlier steps
already test role and ownership rules endpoint by endpoint; this module adds:

  A. A sweep over EVERY registered route, so a new endpoint added without an
     access check fails here instead of going unnoticed.
  B. Token handling: expired, wrong key, unsigned ("none"), unknown user,
     and a role claim that disagrees with the database.
  C. Account status, login error wording, and hostile-looking input.
  D. Password hashes never leave the API.

Same convention as the rest of the suite: real app, real PostgreSQL, every
row created here removed afterward.
"""

import re
from datetime import date, datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.db_models.authentication_user import AuthenticationUser
from app.main import app
from tests.conftest import IDS, TEST_PASSWORD, auth_headers

# The only routes that are meant to work without a token.
PUBLIC_ROUTES = {("GET", "/"), ("GET", "/api/v1/health"), ("POST", "/api/v1/auth/login")}


def _api_routes() -> list[tuple[str, str]]:
    """(method, path) for every route in the API's own OpenAPI description,
    with path parameters filled in by a placeholder. Access checks run before
    the placeholder is ever looked up."""
    return [
        (method.upper(), re.sub(r"\{[^}]+\}", "SECURITY-SWEEP", path))
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    ]


def _protected_routes(prefix: str = "") -> list[tuple[str, str]]:
    return [r for r in _api_routes() if r not in PUBLIC_ROUTES and r[1].startswith(prefix)]


def _signed_token(**overrides) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": IDS["user_customer1"], "role": "Customer", "iat": now, "exp": now + timedelta(minutes=5)}
    payload.update(overrides)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _me(client, token):
    return client.get("/api/v1/auth/me", headers=auth_headers(token))


@pytest.fixture()
def suspended_user(seed_data):
    db = SessionLocal()
    user_id = "TEST-USER-SUSPENDED"
    db.add(
        AuthenticationUser(
            User_ID=user_id, Username="test_suspended", Password_Hash=hash_password(TEST_PASSWORD), Role="Customer",
            Customer_ID=IDS["customer2"], Employee_ID=None, Email="test_suspended@example.com", Phone="9990000009",
            Account_Status="Suspended", Login_Status="Inactive", Last_Login=None, Created_Date=date(2025, 1, 1),
            Failed_Login_Count=0, Permission_Level=1, Insurer_Code=None,
        )
    )
    db.commit()
    db.close()
    yield user_id
    db = SessionLocal()
    db.query(AuthenticationUser).filter(AuthenticationUser.User_ID == user_id).delete()
    db.commit()
    db.close()


# ============================================================== A: every route


def test_only_the_expected_routes_are_public():
    """If this fails, a route was added or renamed: decide whether it is
    meant to be public and update PUBLIC_ROUTES on purpose."""
    assert PUBLIC_ROUTES <= set(_api_routes())
    assert len(_protected_routes()) >= 35


@pytest.mark.parametrize("method,path", _protected_routes(), ids=lambda value: value)
def test_every_protected_route_rejects_a_request_without_a_token(client, method, path):
    assert client.request(method, path).status_code == 401


@pytest.mark.parametrize("method,path", _protected_routes(), ids=lambda value: value)
def test_every_protected_route_rejects_a_garbage_token(client, method, path):
    assert client.request(method, path, headers=auth_headers("not-a-real-token")).status_code == 401


@pytest.mark.parametrize("method,path", _protected_routes("/api/v1/officer"), ids=lambda value: value)
def test_customer_and_surveyor_are_refused_on_every_officer_route(client, customer1_token, surveyor_token, method, path):
    for token in (customer1_token, surveyor_token):
        assert client.request(method, path, headers=auth_headers(token)).status_code == 403


@pytest.mark.parametrize("method,path", _protected_routes("/api/v1/admin"), ids=lambda value: value)
def test_only_admin_passes_the_access_check_on_admin_routes(
    client, customer1_token, surveyor_token, officer_token, method, path
):
    for token in (customer1_token, surveyor_token, officer_token):
        assert client.request(method, path, headers=auth_headers(token)).status_code == 403


@pytest.mark.parametrize("method,path", _protected_routes("/api/v1/surveyor"), ids=lambda value: value)
def test_customer_and_officer_are_refused_on_every_surveyor_route(client, customer1_token, officer_token, method, path):
    for token in (customer1_token, officer_token):
        assert client.request(method, path, headers=auth_headers(token)).status_code == 403


# ============================================================== B: tokens


def test_well_formed_token_is_accepted(client, seed_data):
    """Control case: the helper builds a token the API accepts, so the
    rejections below are caused by the one thing each test changes."""
    assert _me(client, _signed_token()).status_code == 200


def test_expired_token_is_rejected(client, seed_data):
    expired = _signed_token(exp=datetime.now(timezone.utc) - timedelta(minutes=1))
    assert _me(client, expired).status_code == 401


def test_token_signed_with_another_key_is_rejected(client, seed_data):
    payload = {"sub": IDS["user_customer1"], "role": "Customer", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    forged = jwt.encode(payload, "not-the-server-key-not-the-server-key", algorithm=settings.JWT_ALGORITHM)
    assert _me(client, forged).status_code == 401


def test_unsigned_token_is_rejected(client, seed_data):
    payload = {"sub": IDS["user_admin"], "role": "Admin", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    unsigned = jwt.encode(payload, None, algorithm="none")
    assert _me(client, unsigned).status_code == 401


def test_token_for_an_unknown_user_is_rejected(client, seed_data):
    assert _me(client, _signed_token(sub="NO-SUCH-USER")).status_code == 401


def test_token_without_a_subject_is_rejected(client, seed_data):
    assert _me(client, _signed_token(sub="")).status_code == 401


def _signed_token_without(*claims: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": IDS["user_customer1"], "role": "Customer", "iat": now, "exp": now + timedelta(minutes=5)}
    for claim in claims:
        del payload[claim]
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def test_token_without_an_expiry_is_rejected(client, seed_data):
    """Step 5.8.26: a correctly signed token with no `exp` would otherwise
    never expire."""
    assert _me(client, _signed_token_without("exp")).status_code == 401


def test_token_without_a_subject_claim_is_rejected(client, seed_data):
    assert _me(client, _signed_token_without("sub")).status_code == 401


def test_token_issued_by_login_has_an_expiry(client, seed_data, clean_login_throttle):
    token = _login(client, "test_customer1", TEST_PASSWORD).json()["access_token"]
    claims = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    lifetime = claims["exp"] - claims["iat"]
    assert lifetime == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert _me(client, token).status_code == 200


def test_role_comes_from_the_database_not_from_the_token(client, seed_data):
    """A correctly signed token that claims role "Admin" for a Customer
    account still gets a Customer's rights."""
    token = _signed_token(role="Admin")
    assert _me(client, token).json()["Role"] == "Customer"
    assert client.get("/api/v1/admin/users", headers=auth_headers(token)).status_code == 403
    assert client.get("/api/v1/officer/claims", headers=auth_headers(token)).status_code == 403


# ============================================================== C: accounts and input


def test_suspended_account_cannot_log_in(client, suspended_user):
    response = client.post("/api/v1/auth/login", data={"username": "test_suspended", "password": TEST_PASSWORD})
    assert response.status_code == 403
    assert "access_token" not in response.json()


def test_token_of_a_suspended_account_is_refused(client, suspended_user):
    """An account suspended after its token was issued loses access at once."""
    assert _me(client, _signed_token(sub=suspended_user)).status_code == 403


def test_login_error_does_not_reveal_whether_the_username_exists(client, seed_data):
    wrong_password = client.post("/api/v1/auth/login", data={"username": "test_customer2", "password": "wrong-password"})
    unknown_user = client.post("/api/v1/auth/login", data={"username": "no-such-user", "password": "wrong-password"})
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()

    # The failed attempt above is counted; a correct login resets it.
    ok = client.post("/api/v1/auth/login", data={"username": "test_customer2", "password": TEST_PASSWORD})
    assert ok.status_code == 200
    assert _me(client, ok.json()["access_token"]).json()["Failed_Login_Count"] == 0


@pytest.mark.parametrize("username", ["' OR '1'='1", "test_customer1' --", 'admin"; DROP TABLE claims; --'])
def test_sql_looking_username_is_just_a_wrong_username(client, seed_data, username):
    response = client.post("/api/v1/auth/login", data={"username": username, "password": TEST_PASSWORD})
    assert response.status_code == 401


@pytest.mark.parametrize("claim_id", ["' OR '1'='1", "TEST-CLM-0001' --", "1; DROP TABLE claims"])
def test_sql_looking_claim_id_is_just_an_unknown_claim(client, admin_token, seed_data, claim_id):
    assert client.get(f"/api/v1/claims/{claim_id}", headers=auth_headers(admin_token)).status_code == 404
    # The table is still there and still holds the seeded claim.
    assert client.get(f"/api/v1/claims/{seed_data['claim1']}", headers=auth_headers(admin_token)).status_code == 200


# ============================================================== D: password hashes


def test_password_hash_never_leaves_the_api(client, customer1_token, admin_token, seed_data):
    responses = [
        _me(client, customer1_token),
        client.get("/api/v1/admin/users?limit=500", headers=auth_headers(admin_token)),
        client.get(f"/api/v1/admin/users/{seed_data['user_customer1']}", headers=auth_headers(admin_token)),
        client.get("/api/v1/officer/surveyors", headers=auth_headers(admin_token)),
    ]
    for response in responses:
        assert response.status_code == 200
        assert "Password_Hash" not in response.text
        assert "$2b$" not in response.text  # bcrypt hash prefix


# ============================================================== E: Step 5.8.25 login limit


@pytest.fixture()
def clean_login_throttle():
    from app.services import login_throttle

    login_throttle.reset_all()
    yield login_throttle
    login_throttle.reset_all()


def _login(client, username, password):
    return client.post("/api/v1/auth/login", data={"username": username, "password": password})


def test_login_is_refused_after_too_many_wrong_passwords(client, seed_data, clean_login_throttle):
    for _ in range(settings.LOGIN_MAX_FAILED_ATTEMPTS):
        assert _login(client, "test_customer2", "wrong-password").status_code == 401

    # Even the right password is refused now, with a hint of how long to wait.
    blocked = _login(client, "test_customer2", TEST_PASSWORD)
    assert blocked.status_code == 429
    assert "access_token" not in blocked.json()
    assert 0 < int(blocked.headers["Retry-After"]) <= settings.LOGIN_LOCKOUT_MINUTES * 60

    # Another user is not affected, and the username check ignores letter case.
    assert _login(client, "test_customer1", TEST_PASSWORD).status_code == 200
    assert _login(client, "TEST_CUSTOMER2", TEST_PASSWORD).status_code == 429


def test_login_works_again_after_the_waiting_time(client, seed_data, clean_login_throttle):
    throttle = clean_login_throttle
    for _ in range(settings.LOGIN_MAX_FAILED_ATTEMPTS):
        _login(client, "test_customer2", "wrong-password")
    assert _login(client, "test_customer2", TEST_PASSWORD).status_code == 429

    # Move every recorded failure back in time by the waiting period.
    for entry in throttle._entries.values():
        entry.last_failure -= settings.LOGIN_LOCKOUT_MINUTES * 60 + 1
    assert _login(client, "test_customer2", TEST_PASSWORD).status_code == 200


def test_a_correct_login_clears_earlier_wrong_passwords(client, seed_data, clean_login_throttle):
    for _ in range(settings.LOGIN_MAX_FAILED_ATTEMPTS - 1):
        assert _login(client, "test_customer2", "wrong-password").status_code == 401
    assert _login(client, "test_customer2", TEST_PASSWORD).status_code == 200
    # The count started again, so this many more wrong tries are still allowed.
    for _ in range(settings.LOGIN_MAX_FAILED_ATTEMPTS - 1):
        assert _login(client, "test_customer2", "wrong-password").status_code == 401
    assert _login(client, "test_customer2", TEST_PASSWORD).status_code == 200


def test_unknown_usernames_are_limited_too(client, seed_data, clean_login_throttle):
    for _ in range(settings.LOGIN_MAX_FAILED_ATTEMPTS):
        assert _login(client, "no-such-user-at-all", "x").status_code == 401
    assert _login(client, "no-such-user-at-all", "x").status_code == 429


def test_login_limit_counts_each_client_address_separately(clean_login_throttle):
    throttle = clean_login_throttle
    attacker, owner = throttle.make_key("Some_User", "10.0.0.1"), throttle.make_key("some_user", "10.0.0.2")
    for _ in range(settings.LOGIN_MAX_FAILED_ATTEMPTS):
        throttle.record_failure(attacker)
    assert throttle.seconds_until_allowed(attacker) > 0
    assert throttle.seconds_until_allowed(owner) == 0
