from tests.conftest import auth_headers


def test_customer_can_read_own_claim(client, customer1_token, seed_data):
    response = client.get(
        f"/api/v1/claims/{seed_data['claim1']}", headers=auth_headers(customer1_token)
    )
    assert response.status_code == 200
    assert response.json()["Claim_ID"] == seed_data["claim1"]


def test_customer_cannot_access_another_customers_claim(client, customer2_token, seed_data):
    """customer2 must not be able to read customer1's claim."""
    response = client.get(
        f"/api/v1/claims/{seed_data['claim1']}", headers=auth_headers(customer2_token)
    )
    assert response.status_code == 403


def test_customer_claim_list_only_contains_own_claims(client, customer1_token, seed_data):
    response = client.get("/api/v1/claims", headers=auth_headers(customer1_token))
    assert response.status_code == 200
    claim_ids = {c["Claim_ID"] for c in response.json()}
    assert seed_data["claim1"] in claim_ids


def test_customer_cannot_use_officer_endpoint(client, customer1_token, seed_data):
    response = client.get("/api/v1/officer/claims", headers=auth_headers(customer1_token))
    assert response.status_code == 403


def test_surveyor_can_read_assigned_claim(client, surveyor_token, seed_data):
    response = client.get(
        f"/api/v1/claims/{seed_data['claim1']}", headers=auth_headers(surveyor_token)
    )
    assert response.status_code == 200


def test_surveyor_sees_assigned_claim_in_inspections(client, surveyor_token, seed_data):
    response = client.get("/api/v1/surveyor/inspections", headers=auth_headers(surveyor_token))
    assert response.status_code == 200
    inspection_ids = {i["Inspection_ID"] for i in response.json()}
    assert seed_data["inspection1"] in inspection_ids


def test_surveyor_cannot_use_admin_endpoint(client, surveyor_token, seed_data):
    response = client.get("/api/v1/admin/users", headers=auth_headers(surveyor_token))
    assert response.status_code == 403


def test_officer_can_read_any_claim(client, officer_token, seed_data):
    response = client.get(
        f"/api/v1/officer/claims/{seed_data['claim1']}", headers=auth_headers(officer_token)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["claim"]["Claim_ID"] == seed_data["claim1"]
    assert "surveyor_inspections" in body
    assert "accidents" in body
    assert "evidence" in body


def test_officer_cannot_use_admin_endpoint(client, officer_token, seed_data):
    response = client.get("/api/v1/admin/users", headers=auth_headers(officer_token))
    assert response.status_code == 403


def test_admin_can_list_users(client, admin_token, seed_data):
    response = client.get("/api/v1/admin/users", headers=auth_headers(admin_token))
    assert response.status_code == 200
    usernames = {u["Username"] for u in response.json()}
    assert "test_customer1" in usernames
    for user in response.json():
        assert "Password_Hash" not in user


def test_admin_can_read_any_claim(client, admin_token, seed_data):
    response = client.get(
        f"/api/v1/claims/{seed_data['claim1']}", headers=auth_headers(admin_token)
    )
    assert response.status_code == 200


def test_claim_not_found_returns_404(client, admin_token, seed_data):
    response = client.get("/api/v1/claims/NO-SUCH-CLAIM", headers=auth_headers(admin_token))
    assert response.status_code == 404
