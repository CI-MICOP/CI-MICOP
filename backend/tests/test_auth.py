from tests.conftest import TEST_PASSWORD, auth_headers


def test_login_success(client, seed_data):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "test_customer1", "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_invalid_password(client, seed_data):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "test_customer1", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_login_unknown_username(client, seed_data):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "no-such-user", "password": TEST_PASSWORD},
    )
    assert response.status_code == 401


def test_jwt_required_for_protected_endpoint(client, seed_data):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_jwt_rejected_when_invalid(client, seed_data):
    response = client.get("/api/v1/auth/me", headers=auth_headers("not-a-real-token"))
    assert response.status_code == 401


def test_jwt_accepted_returns_current_user(client, customer1_token):
    response = client.get("/api/v1/auth/me", headers=auth_headers(customer1_token))
    assert response.status_code == 200
    body = response.json()
    assert body["Username"] == "test_customer1"
    assert body["Role"] == "Customer"
    assert "Password_Hash" not in body
