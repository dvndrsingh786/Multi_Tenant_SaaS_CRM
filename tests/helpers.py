"""Small functions that many tests use."""
from sqlalchemy import text

PASSWORD = "Password123!"


def register_company(client, company_name="Acme Ltd", email="admin@acme.com", name="Alice Admin"):
    response = client.post("/api/v1/auth/register", json={
        "company_name": company_name,
        "name": name,
        "email": email,
        "password": PASSWORD,
    })
    assert response.status_code == 201, response.text
    return response.json()


def login(client, email, password=PASSWORD):
    """Log in and return the headers to send with the next requests."""
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_user(client, admin_headers, email, role, name="Test User"):
    response = client.post("/api/v1/users", headers=admin_headers, json={
        "name": name,
        "email": email,
        "password": PASSWORD,
        "role": role,
    })
    assert response.status_code == 201, response.text
    return response.json()


def set_plan(engine, company_id, plan_name):
    """Change a company's plan directly in the database (there is no API endpoint for it)."""
    with engine.begin() as db:
        db.execute(text("""
            UPDATE subscriptions SET plan_id = (SELECT id FROM plans WHERE name = :plan)
            WHERE company_id = :company_id
        """), {"plan": plan_name, "company_id": company_id})


def create_company_with_team(client, engine, company_name, domain):
    """Make a company with an admin, a manager and two sales agents, all logged in.

    Returns a dict like:
        {"company_id": 1,
         "admin":   {"id": 1, "headers": {...}},
         "manager": {"id": 2, "headers": {...}},
         "agent1":  {...}, "agent2": {...}}
    """
    registered = register_company(client, company_name, email=f"admin@{domain}")
    admin_headers = login(client, f"admin@{domain}")

    # The FREE plan only allows 3 users and we need 4, so move to STARTER.
    set_plan(engine, registered["company_id"], "STARTER")

    team = {
        "company_id": registered["company_id"],
        "admin": {"id": registered["user"]["id"], "headers": admin_headers},
    }
    for key, role in [("manager", "MANAGER"), ("agent1", "SALES_AGENT"), ("agent2", "SALES_AGENT")]:
        email = f"{key}@{domain}"
        new_user = create_user(client, admin_headers, email, role, name=key.title())
        team[key] = {"id": new_user["id"], "headers": login(client, email)}
    return team
