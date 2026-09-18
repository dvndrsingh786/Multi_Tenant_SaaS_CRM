"""Tests for the dashboard, global search and audit logs."""


def add_lead(client, headers, **fields):
    data = {"first_name": "John", "last_name": "Smith"}
    data.update(fields)
    response = client.post("/api/v1/leads", headers=headers, json=data)
    assert response.status_code == 201, response.text
    return response.json()


def add_deal(client, headers, **fields):
    response = client.post("/api/v1/deals", headers=headers, json=fields)
    assert response.status_code == 201, response.text
    return response.json()


# ---------- Dashboard ----------

def test_dashboard_totals(client, acme):
    headers = acme["admin"]["headers"]
    add_lead(client, headers, status="NEW")
    add_lead(client, headers, status="NEW")
    add_lead(client, headers, status="QUALIFIED")
    lead = add_lead(client, headers, status="LOST")
    client.post(f"/api/v1/leads/{lead['id']}/convert", headers=headers)  # becomes WON + 1 customer
    add_deal(client, headers, title="Open deal", value=1000, stage="PROPOSAL")
    add_deal(client, headers, title="Won deal", value=2500, stage="WON")
    add_deal(client, headers, title="Lost deal", value=999, stage="LOST")

    body = client.get("/api/v1/dashboard", headers=headers).json()

    assert body["total_leads"] == 4
    assert body["new_leads"] == 2
    assert body["qualified_leads"] == 1
    assert body["won_leads"] == 1
    assert body["lost_leads"] == 0
    assert body["leads_by_status"]["CONTACTED"] == 0
    assert body["total_customers"] == 1
    assert body["total_deals"] == 3
    assert body["pipeline_value"] == 1000
    assert body["won_value"] == 2500


def test_dashboard_for_sales_agent_only_counts_their_records(client, acme):
    add_lead(client, acme["agent1"]["headers"])
    add_lead(client, acme["agent2"]["headers"])
    add_lead(client, acme["agent2"]["headers"])
    add_deal(client, acme["agent2"]["headers"], title="Theirs", value=500)

    body = client.get("/api/v1/dashboard", headers=acme["agent1"]["headers"]).json()
    assert body["total_leads"] == 1
    assert body["total_deals"] == 0

    body = client.get("/api/v1/dashboard", headers=acme["manager"]["headers"]).json()
    assert body["total_leads"] == 3


def test_dashboard_is_separate_per_company(client, acme, globex):
    add_lead(client, acme["admin"]["headers"])
    add_deal(client, acme["admin"]["headers"], title="Acme deal", value=100, stage="WON")

    body = client.get("/api/v1/dashboard", headers=globex["admin"]["headers"]).json()
    assert body["total_leads"] == 0
    assert body["won_value"] == 0


# ---------- Search ----------

def test_search_finds_all_types_case_insensitive(client, acme):
    headers = acme["admin"]["headers"]
    add_lead(client, headers, first_name="Johnathan", last_name="Lead")
    client.post("/api/v1/contacts", headers=headers, json={"first_name": "Johnny", "last_name": "Contact"})
    client.post("/api/v1/customers", headers=headers, json={"first_name": "John", "last_name": "Customer"})
    add_deal(client, headers, title="John's new website")
    add_lead(client, headers, first_name="Mary", last_name="Nomatch")

    response = client.get("/api/v1/search", headers=headers, params={"q": "JOHN"})

    assert response.status_code == 200
    types = sorted(result["type"] for result in response.json()["data"])
    assert types == ["contact", "customer", "deal", "lead"]
    assert response.json()["meta"]["total"] == 4


def test_search_type_filter_and_pagination(client, acme):
    headers = acme["admin"]["headers"]
    for number in range(3):
        add_lead(client, headers, first_name=f"Sam{number}")

    response = client.get("/api/v1/search", headers=headers, params={"q": "sam", "type": "lead", "per_page": 2})
    assert len(response.json()["data"]) == 2
    assert response.json()["meta"]["total_pages"] == 2


def test_search_never_returns_other_company_records(client, acme, globex):
    add_lead(client, acme["admin"]["headers"], first_name="Secretname")
    response = client.get("/api/v1/search", headers=globex["admin"]["headers"], params={"q": "secretname"})
    assert response.json()["data"] == []


def test_search_respects_sales_agent_visibility(client, acme):
    add_lead(client, acme["agent2"]["headers"], first_name="Hiddenlead")
    response = client.get("/api/v1/search", headers=acme["agent1"]["headers"], params={"q": "hiddenlead"})
    assert response.json()["data"] == []


def test_search_needs_at_least_2_characters(client, acme):
    response = client.get("/api/v1/search", headers=acme["admin"]["headers"], params={"q": "a"})
    assert response.status_code == 422


# ---------- Audit logs ----------

def test_admin_can_read_audit_logs_with_filters(client, acme):
    headers = acme["admin"]["headers"]
    lead = add_lead(client, headers)
    client.patch(f"/api/v1/leads/{lead['id']}", headers=headers, json={"status": "CONTACTED"})

    response = client.get("/api/v1/audit-logs", headers=headers,
                          params={"entity_type": "lead", "entity_id": lead["id"]})

    assert response.status_code == 200
    logs = response.json()["data"]
    assert [log["action"] for log in logs] == ["UPDATE", "CREATE"]  # newest first
    assert logs[0]["old_values"]["status"] == "NEW"
    assert logs[0]["new_values"]["status"] == "CONTACTED"


def test_audit_logs_never_contain_passwords(client, acme):
    response = client.get("/api/v1/audit-logs", headers=acme["admin"]["headers"],
                          params={"entity_type": "user", "per_page": 100})
    assert "password" not in response.text


def test_only_admin_can_read_audit_logs(client, acme):
    assert client.get("/api/v1/audit-logs", headers=acme["manager"]["headers"]).status_code == 403
    assert client.get("/api/v1/audit-logs", headers=acme["agent1"]["headers"]).status_code == 403


def test_audit_logs_are_separate_per_company(client, acme, globex):
    add_lead(client, acme["admin"]["headers"], first_name="AcmeOnly")
    response = client.get("/api/v1/audit-logs", headers=globex["admin"]["headers"], params={"per_page": 100})
    assert "AcmeOnly" not in response.text
    assert all(log["user_id"] != acme["admin"]["id"] for log in response.json()["data"])
