from sqlalchemy import text

from helpers import PASSWORD, create_user, login, register_company, set_plan


def test_free_plan_allows_only_3_users(client):
    register_company(client, email="boss@small.com")  # the admin is user 1
    headers = login(client, "boss@small.com")
    create_user(client, headers, "one@small.com", "SALES_AGENT")
    create_user(client, headers, "two@small.com", "SALES_AGENT")

    response = client.post("/api/v1/users", headers=headers, json={
        "name": "Fourth", "email": "three@small.com", "password": PASSWORD, "role": "SALES_AGENT",
    })

    assert response.status_code == 403
    assert "FREE plan allows 3 users" in response.json()["detail"]


def test_free_plan_allows_only_100_leads(client, test_engine):
    registered = register_company(client, email="boss@small.com")
    headers = login(client, "boss@small.com")

    # Insert 100 leads directly in the database to keep the test fast.
    with test_engine.begin() as db:
        for number in range(100):
            db.execute(text("INSERT INTO leads (company_id, first_name, last_name) VALUES (:c, 'Lead', :n)"),
                       {"c": registered["company_id"], "n": str(number)})

    response = client.post("/api/v1/leads", headers=headers, json={"first_name": "One", "last_name": "Toomany"})

    assert response.status_code == 403
    assert "FREE plan allows 100 leads" in response.json()["detail"]


def test_bigger_plan_allows_more_users(client, test_engine):
    registered = register_company(client, email="boss@small.com")
    headers = login(client, "boss@small.com")
    create_user(client, headers, "one@small.com", "SALES_AGENT")
    create_user(client, headers, "two@small.com", "SALES_AGENT")

    set_plan(test_engine, registered["company_id"], "PRO")

    create_user(client, headers, "three@small.com", "SALES_AGENT")  # would fail on FREE
