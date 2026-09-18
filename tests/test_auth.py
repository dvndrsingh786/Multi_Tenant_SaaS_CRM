import pytest
from sqlalchemy import text

from app.security import verify_password
from helpers import PASSWORD, login, register_company

REGISTER_URL = "/api/v1/auth/register"


def valid_registration():
    return {
        "company_name": "Acme Ltd",
        "name": "John Smith",
        "email": "john@acme.com",
        "password": "SecurePassword123!",
    }


# ---------- Register ----------

def test_register_creates_company_admin_and_free_plan(client, test_engine):
    response = client.post(REGISTER_URL, json=valid_registration())

    assert response.status_code == 201
    body = response.json()
    assert body["company_name"] == "Acme Ltd"
    assert body["user"]["role"] == "ADMIN"
    assert "password" not in response.text

    with test_engine.connect() as db:
        user = db.execute(text("SELECT * FROM users")).mappings().one()
        plan = db.execute(text("""
            SELECT plans.name FROM subscriptions JOIN plans ON plans.id = subscriptions.plan_id
            WHERE subscriptions.company_id = :id
        """), {"id": body["company_id"]}).scalar_one()

    assert user["company_id"] == body["company_id"]
    assert user["password_hash"] != "SecurePassword123!"
    assert verify_password("SecurePassword123!", user["password_hash"])
    assert plan == "FREE"


def test_register_with_same_email_returns_409(client, test_engine):
    assert client.post(REGISTER_URL, json=valid_registration()).status_code == 201

    data = valid_registration()
    data["email"] = "JOHN@acme.com"  # same email, different capital letters
    response = client.post(REGISTER_URL, json=data)

    assert response.status_code == 409
    with test_engine.connect() as db:
        assert db.execute(text("SELECT COUNT(*) FROM companies")).scalar() == 1


@pytest.mark.parametrize("bad_fields", [
    {"company_name": "   "},
    {"name": ""},
    {"email": "not-an-email"},
    {"password": "short1"},
    {"password": "onlyletters"},
    {"role": "ADMIN"},          # extra field -> rejected
    {"company_id": 5},          # extra field -> rejected
])
def test_register_with_bad_data_returns_422(client, test_engine, bad_fields):
    data = valid_registration()
    data.update(bad_fields)

    response = client.post(REGISTER_URL, json=data)

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"]
    with test_engine.connect() as db:
        assert db.execute(text("SELECT COUNT(*) FROM companies")).scalar() == 0


def test_validation_errors_do_not_echo_the_password(client):
    data = valid_registration()
    data["password"] = "nonumbersatall"
    response = client.post(REGISTER_URL, json=data)
    assert response.status_code == 422
    assert "nonumbersatall" not in response.text


# ---------- Login, me, logout ----------

def test_login_and_me(client):
    register_company(client, email="admin@acme.com")

    headers = login(client, "admin@acme.com")
    response = client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "admin@acme.com"
    assert response.json()["role"] == "ADMIN"


def test_login_with_wrong_password_returns_401(client):
    register_company(client, email="admin@acme.com")
    response = client.post("/api/v1/auth/login", json={"email": "admin@acme.com", "password": "Wrong123!"})
    assert response.status_code == 401


def test_login_with_unknown_email_returns_401(client):
    response = client.post("/api/v1/auth/login", json={"email": "nobody@acme.com", "password": PASSWORD})
    assert response.status_code == 401


def test_me_without_token_returns_401(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_with_fake_token_returns_401(client):
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer made-up-token"})
    assert response.status_code == 401


def test_logout_makes_the_token_useless(client):
    register_company(client, email="admin@acme.com")
    headers = login(client, "admin@acme.com")

    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_login_and_logout_are_audit_logged(client, test_engine):
    register_company(client, email="admin@acme.com")
    headers = login(client, "admin@acme.com")
    client.post("/api/v1/auth/logout", headers=headers)

    with test_engine.connect() as db:
        actions = db.execute(text("SELECT action FROM audit_logs ORDER BY id")).scalars().all()
    assert "LOGIN" in actions
    assert "LOGOUT" in actions


def test_login_is_rate_limited(client):
    register_company(client, email="admin@acme.com")
    wrong_login = {"email": "admin@acme.com", "password": "Wrong123!"}

    for _ in range(5):
        assert client.post("/api/v1/auth/login", json=wrong_login).status_code == 401

    response = client.post("/api/v1/auth/login", json=wrong_login)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
