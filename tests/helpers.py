"""Small functions that many tests use."""

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


def create_company_with_team(client, company_name, domain):
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
    response = client.patch("/api/v1/subscription", headers=admin_headers, json={"plan": "STARTER"})
    assert response.status_code == 200, response.text

    team = {
        "company_id": registered["company_id"],
        "admin": {"id": registered["user"]["id"], "headers": admin_headers},
    }
    for key, role in [("manager", "MANAGER"), ("agent1", "SALES_AGENT"), ("agent2", "SALES_AGENT")]:
        email = f"{key}@{domain}"
        new_user = create_user(client, admin_headers, email, role, name=key.title())
        team[key] = {"id": new_user["id"], "headers": login(client, email)}
    return team
