from helpers import create_user, login, register_company, set_plan


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


def test_bigger_plan_allows_more_users(client, test_engine):
    registered = register_company(client, email="boss@small.com")
    headers = login(client, "boss@small.com")
    create_user(client, headers, "one@small.com", "SALES_AGENT")
    create_user(client, headers, "two@small.com", "SALES_AGENT")

    set_plan(test_engine, registered["company_id"], "PRO")

    create_user(client, headers, "three@small.com", "SALES_AGENT")  # would fail on FREE


def test_enterprise_plan_has_no_user_limit(client, test_engine):
    registered = register_company(client, email="boss@big.com")
    headers = login(client, "boss@big.com")
    set_plan(test_engine, registered["company_id"], "ENTERPRISE")

    for number in range(12):  # more than STARTER (10) allows
        create_user(client, headers, f"user{number}@big.com", "SALES_AGENT")
