"""Company B must never be able to read, change, delete or find company A's data.

(Leads and users have their own isolation tests in test_leads.py and test_users.py.)
"""


def create(client, headers, url, data):
    response = client.post(url, headers=headers, json=data)
    assert response.status_code == 201, response.text
    return response.json()


def test_customers_are_isolated(client, acme, globex):
    customer = create(client, acme["admin"]["headers"], "/api/v1/customers",
                      {"first_name": "AcmeOnly", "last_name": "Customer"})
    url = f"/api/v1/customers/{customer['id']}"
    headers = globex["admin"]["headers"]

    assert client.get(url, headers=headers).status_code == 404
    assert client.patch(url, headers=headers, json={"first_name": "Hacked"}).status_code == 404
    assert client.delete(url, headers=headers).status_code == 404
    assert client.get("/api/v1/customers", headers=headers).json()["meta"]["total"] == 0


def test_contacts_are_isolated(client, acme, globex):
    contact = create(client, acme["admin"]["headers"], "/api/v1/contacts",
                     {"first_name": "Cara", "last_name": "Contact"})
    url = f"/api/v1/contacts/{contact['id']}"
    headers = globex["admin"]["headers"]

    assert client.get(url, headers=headers).status_code == 404
    assert client.patch(url, headers=headers, json={"first_name": "Hacked"}).status_code == 404
    assert client.delete(url, headers=headers).status_code == 404
    assert client.get("/api/v1/contacts", headers=headers).json()["meta"]["total"] == 0


def test_deals_are_isolated(client, acme, globex):
    deal = create(client, acme["admin"]["headers"], "/api/v1/deals", {"title": "Acme deal", "value": 5000})
    url = f"/api/v1/deals/{deal['id']}"
    headers = globex["admin"]["headers"]

    assert client.get(url, headers=headers).status_code == 404
    assert client.patch(url, headers=headers, json={"title": "Hacked"}).status_code == 404
    assert client.patch(f"{url}/stage", headers=headers, json={"stage": "LOST"}).status_code == 404
    assert client.delete(url, headers=headers).status_code == 404


def test_activities_are_isolated(client, acme, globex):
    activity = create(client, acme["admin"]["headers"], "/api/v1/activities", {"type": "CALL", "title": "Intro call"})
    url = f"/api/v1/activities/{activity['id']}"
    headers = globex["admin"]["headers"]

    assert client.get(url, headers=headers).status_code == 404
    assert client.patch(url, headers=headers, json={"title": "Hacked"}).status_code == 404
    assert client.get("/api/v1/activities", headers=headers).json()["meta"]["total"] == 0


def test_search_never_returns_other_company_records(client, acme, globex):
    create(client, acme["admin"]["headers"], "/api/v1/leads", {"first_name": "Secretname", "last_name": "Lead"})

    response = client.get("/api/v1/search", headers=globex["admin"]["headers"], params={"q": "secretname"})
    assert response.json()["data"] == []


def test_dashboard_only_counts_own_company(client, acme, globex):
    create(client, acme["admin"]["headers"], "/api/v1/leads", {"first_name": "John", "last_name": "Smith"})
    create(client, acme["admin"]["headers"], "/api/v1/deals", {"title": "Acme deal", "value": 100, "stage": "WON"})

    body = client.get("/api/v1/dashboard", headers=globex["admin"]["headers"]).json()
    assert body["total_leads"] == 0
    assert body["won_value"] == 0

    body = client.get("/api/v1/dashboard", headers=acme["admin"]["headers"]).json()
    assert body["total_leads"] == 1
    assert body["won_value"] == 100


def test_audit_logs_only_for_admin_and_own_company(client, acme, globex):
    create(client, acme["admin"]["headers"], "/api/v1/leads", {"first_name": "AcmeOnly", "last_name": "Lead"})

    assert client.get("/api/v1/audit-logs", headers=acme["manager"]["headers"]).status_code == 403
    assert client.get("/api/v1/audit-logs", headers=acme["agent1"]["headers"]).status_code == 403

    response = client.get("/api/v1/audit-logs", headers=globex["admin"]["headers"], params={"per_page": 100})
    assert "AcmeOnly" not in response.text
    assert all(log["user_id"] != acme["admin"]["id"] for log in response.json()["data"])
