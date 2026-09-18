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
