from helpers import create_user, login, register_company


def test_every_user_sees_their_own_company(client, acme, globex):
    response = client.get("/api/v1/company", headers=acme["agent1"]["headers"])
    assert response.status_code == 200
    assert response.json()["name"] == "Acme Ltd"

    response = client.get("/api/v1/company", headers=globex["agent1"]["headers"])
    assert response.json()["name"] == "Globex Corp"


def test_admin_can_update_company(client, acme):
    response = client.patch("/api/v1/company", headers=acme["admin"]["headers"],
                            json={"phone": "+44 20 1234 5678", "website": "https://acme.example"})
    assert response.status_code == 200
    assert response.json()["phone"] == "+44 20 1234 5678"


def test_manager_cannot_update_company(client, acme):
    response = client.patch("/api/v1/company", headers=acme["manager"]["headers"], json={"name": "New name"})
    assert response.status_code == 403


def test_company_cannot_change_its_own_status(client, acme):
    response = client.patch("/api/v1/company", headers=acme["admin"]["headers"], json={"status": "SUSPENDED"})
    assert response.status_code == 422


def test_company_name_cannot_be_set_to_null(client, acme):
    response = client.patch("/api/v1/company", headers=acme["admin"]["headers"], json={"name": None})
    assert response.status_code == 422


def test_subscription_shows_plan_and_usage(client, acme):
    response = client.get("/api/v1/subscription", headers=acme["admin"]["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["name"] == "STARTER"
    assert body["users_used"] == 4


def test_cannot_downgrade_below_current_usage(client, acme):
    # Acme has 4 users, FREE allows 3.
    response = client.patch("/api/v1/subscription", headers=acme["admin"]["headers"], json={"plan": "FREE"})
    assert response.status_code == 409


def test_only_admin_can_change_plan(client, acme):
    response = client.patch("/api/v1/subscription", headers=acme["manager"]["headers"], json={"plan": "PRO"})
    assert response.status_code == 403


def test_upgrade_raises_the_user_limit(client):
    register_company(client, email="boss@small.com")
    headers = login(client, "boss@small.com")
    create_user(client, headers, "one@small.com", "SALES_AGENT")
    create_user(client, headers, "two@small.com", "SALES_AGENT")

    client.patch("/api/v1/subscription", headers=headers, json={"plan": "PRO"})

    create_user(client, headers, "three@small.com", "SALES_AGENT")  # would fail on FREE


def test_plans_list(client, acme):
    response = client.get("/api/v1/plans", headers=acme["agent1"]["headers"])
    names = [plan["name"] for plan in response.json()]
    assert names == ["FREE", "STARTER", "PRO", "ENTERPRISE"]
