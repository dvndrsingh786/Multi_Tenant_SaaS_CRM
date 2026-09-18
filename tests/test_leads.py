from sqlalchemy import text

from helpers import login, register_company

LEADS_URL = "/api/v1/leads"


def make_lead(client, headers, **fields):
    data = {"first_name": "John", "last_name": "Smith"}
    data.update(fields)
    response = client.post(LEADS_URL, headers=headers, json=data)
    assert response.status_code == 201, response.text
    return response.json()


# ---------- CRUD ----------

def test_create_and_read_lead(client, acme):
    headers = acme["admin"]["headers"]
    lead = make_lead(client, headers, email="john@example.com", source="WEBSITE", estimated_value=1500.5)

    assert lead["company_id"] == acme["company_id"]
    assert lead["status"] == "NEW"
    assert lead["estimated_value"] == 1500.5

    response = client.get(f"{LEADS_URL}/{lead['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "john@example.com"


def test_update_lead(client, acme):
    headers = acme["admin"]["headers"]
    lead = make_lead(client, headers)

    response = client.patch(f"{LEADS_URL}/{lead['id']}", headers=headers,
                            json={"status": "QUALIFIED", "phone": "07700 900123"})
    assert response.status_code == 200
    assert response.json()["status"] == "QUALIFIED"
    assert response.json()["phone"] == "07700 900123"
    assert response.json()["first_name"] == "John"  # unchanged


def test_delete_lead_is_soft_delete(client, acme, test_engine):
    headers = acme["admin"]["headers"]
    lead = make_lead(client, headers)

    assert client.delete(f"{LEADS_URL}/{lead['id']}", headers=headers).status_code == 204
    assert client.get(f"{LEADS_URL}/{lead['id']}", headers=headers).status_code == 404

    # The row is still in the database, only marked as deleted.
    with test_engine.connect() as db:
        deleted_at = db.execute(text("SELECT deleted_at FROM leads WHERE id = :id"), {"id": lead["id"]}).scalar()
    assert deleted_at is not None


def test_lead_changes_are_audit_logged(client, acme, test_engine):
    headers = acme["admin"]["headers"]
    lead = make_lead(client, headers)
    client.patch(f"{LEADS_URL}/{lead['id']}", headers=headers, json={"status": "CONTACTED"})
    client.delete(f"{LEADS_URL}/{lead['id']}", headers=headers)

    with test_engine.connect() as db:
        actions = db.execute(text(
            "SELECT action FROM audit_logs WHERE entity_type = 'lead' AND entity_id = :id ORDER BY id"
        ), {"id": lead["id"]}).scalars().all()
    assert actions == ["CREATE", "UPDATE", "DELETE"]


# ---------- Validation ----------

def test_invalid_lead_data_returns_422_with_field_errors(client, acme):
    response = client.post(LEADS_URL, headers=acme["admin"]["headers"], json={
        "first_name": "",
        "last_name": "Smith",
        "status": "MAYBE",
        "estimated_value": -5,
    })
    assert response.status_code == 422
    fields = {error["field"] for error in response.json()["errors"]}
    assert {"first_name", "status", "estimated_value"} <= fields


def test_unknown_fields_are_rejected(client, acme, globex):
    response = client.post(LEADS_URL, headers=acme["admin"]["headers"], json={
        "first_name": "John", "last_name": "Smith", "company_id": globex["company_id"],
    })
    assert response.status_code == 422


def test_assigned_to_cannot_be_changed_with_patch(client, acme):
    lead = make_lead(client, acme["admin"]["headers"])
    response = client.patch(f"{LEADS_URL}/{lead['id']}", headers=acme["admin"]["headers"],
                            json={"assigned_to": acme["agent1"]["id"]})
    assert response.status_code == 422


# ---------- Permissions ----------

def test_sales_agent_only_sees_their_own_leads(client, acme):
    make_lead(client, acme["admin"]["headers"], first_name="Unassigned")
    make_lead(client, acme["admin"]["headers"], first_name="ForAgent2", assigned_to=acme["agent2"]["id"])
    own = make_lead(client, acme["agent1"]["headers"], first_name="Mine")

    response = client.get(LEADS_URL, headers=acme["agent1"]["headers"])
    assert [lead["first_name"] for lead in response.json()["data"]] == ["Mine"]
    assert own["assigned_to"] == acme["agent1"]["id"]


def test_sales_agent_cannot_open_someone_elses_lead(client, acme):
    other = make_lead(client, acme["admin"]["headers"], assigned_to=acme["agent2"]["id"])
    headers = acme["agent1"]["headers"]

    assert client.get(f"{LEADS_URL}/{other['id']}", headers=headers).status_code == 404
    assert client.patch(f"{LEADS_URL}/{other['id']}", headers=headers, json={"status": "LOST"}).status_code == 404


def test_sales_agent_cannot_create_lead_for_someone_else(client, acme):
    response = client.post(LEADS_URL, headers=acme["agent1"]["headers"], json={
        "first_name": "John", "last_name": "Smith", "assigned_to": acme["agent2"]["id"],
    })
    assert response.status_code == 403


def test_only_admin_can_delete(client, acme):
    lead = make_lead(client, acme["agent1"]["headers"])
    url = f"{LEADS_URL}/{lead['id']}"

    assert client.delete(url, headers=acme["agent1"]["headers"]).status_code == 403
    assert client.delete(url, headers=acme["manager"]["headers"]).status_code == 403
    assert client.delete(url, headers=acme["admin"]["headers"]).status_code == 204


def test_manager_sees_all_company_leads(client, acme):
    make_lead(client, acme["agent1"]["headers"])
    make_lead(client, acme["agent2"]["headers"])
    response = client.get(LEADS_URL, headers=acme["manager"]["headers"])
    assert response.json()["meta"]["total"] == 2


# ---------- Tenant isolation ----------

def test_other_company_cannot_read_update_or_delete_lead(client, acme, globex):
    lead = make_lead(client, acme["admin"]["headers"], first_name="Secret")
    url = f"{LEADS_URL}/{lead['id']}"
    headers = globex["admin"]["headers"]

    assert client.get(url, headers=headers).status_code == 404
    assert client.patch(url, headers=headers, json={"first_name": "Hacked"}).status_code == 404
    assert client.delete(url, headers=headers).status_code == 404

    # Still there and unchanged for Acme.
    response = client.get(url, headers=acme["admin"]["headers"])
    assert response.json()["first_name"] == "Secret"


def test_list_and_search_never_show_other_company_leads(client, acme, globex):
    make_lead(client, acme["admin"]["headers"], first_name="John", last_name="Acme")
    make_lead(client, globex["admin"]["headers"], first_name="John", last_name="Globex")

    response = client.get(LEADS_URL, headers=globex["admin"]["headers"], params={"search": "john"})
    assert [lead["last_name"] for lead in response.json()["data"]] == ["Globex"]


def test_cannot_assign_lead_to_user_of_another_company(client, acme, globex):
    lead = make_lead(client, acme["admin"]["headers"])
    response = client.patch(f"{LEADS_URL}/{lead['id']}/assign", headers=acme["admin"]["headers"],
                            json={"user_id": globex["agent1"]["id"]})
    assert response.status_code == 422


def test_cannot_create_lead_assigned_to_user_of_another_company(client, acme, globex):
    response = client.post(LEADS_URL, headers=acme["admin"]["headers"], json={
        "first_name": "John", "last_name": "Smith", "assigned_to": globex["agent1"]["id"],
    })
    assert response.status_code == 422


def test_cannot_add_note_to_other_company_lead(client, acme, globex):
    lead = make_lead(client, acme["admin"]["headers"])
    response = client.post(f"{LEADS_URL}/{lead['id']}/notes", headers=globex["admin"]["headers"],
                           json={"content": "sneaky"})
    assert response.status_code == 404


# ---------- Search, filters, sorting, pagination ----------

def test_search_filter_sort_and_paginate(client, acme):
    headers = acme["admin"]["headers"]
    make_lead(client, headers, first_name="John", last_name="Brown", status="QUALIFIED",
              source="WEBSITE", estimated_value=100, assigned_to=acme["agent1"]["id"])
    make_lead(client, headers, first_name="Johnny", last_name="White", status="QUALIFIED",
              source="WEBSITE", estimated_value=300, assigned_to=acme["agent1"]["id"])
    make_lead(client, headers, first_name="Mary", last_name="Green", status="NEW", source="REFERRAL")

    # Search is case-insensitive.
    response = client.get(LEADS_URL, headers=headers, params={"search": "JOHN"})
    assert response.json()["meta"]["total"] == 2

    # All the filters from the brief together.
    response = client.get(LEADS_URL, headers=headers, params={
        "page": 1, "per_page": 25, "search": "john", "status": "QUALIFIED", "source": "WEBSITE",
        "assigned_to": acme["agent1"]["id"], "sort_by": "estimated_value", "sort_order": "desc",
    })
    assert [lead["first_name"] for lead in response.json()["data"]] == ["Johnny", "John"]

    # Pagination.
    response = client.get(LEADS_URL, headers=headers, params={"per_page": 2, "page": 2, "sort_by": "first_name",
                                                            "sort_order": "asc"})
    assert [lead["first_name"] for lead in response.json()["data"]] == ["Mary"]
    assert response.json()["meta"] == {"page": 2, "per_page": 2, "total": 3, "total_pages": 2}


def test_bad_list_parameters_return_422(client, acme):
    headers = acme["admin"]["headers"]
    assert client.get(LEADS_URL, headers=headers, params={"per_page": 5000}).status_code == 422
    assert client.get(LEADS_URL, headers=headers, params={"page": 0}).status_code == 422
    assert client.get(LEADS_URL, headers=headers, params={"page": 10**18}).status_code == 422
    assert client.get(LEADS_URL, headers=headers, params={"sort_by": "password_hash"}).status_code == 422
    assert client.get(LEADS_URL, headers=headers, params={"status": "WHATEVER"}).status_code == 422


def test_search_with_percent_sign_is_not_a_wildcard(client, acme):
    make_lead(client, acme["admin"]["headers"])
    response = client.get(LEADS_URL, headers=acme["admin"]["headers"], params={"search": "%"})
    assert response.json()["meta"]["total"] == 0


# ---------- Assignment ----------

def test_manager_can_assign_a_lead(client, acme, test_engine):
    lead = make_lead(client, acme["admin"]["headers"])
    response = client.patch(f"{LEADS_URL}/{lead['id']}/assign", headers=acme["manager"]["headers"],
                            json={"user_id": acme["agent1"]["id"]})
    assert response.status_code == 200
    assert response.json()["assigned_to"] == acme["agent1"]["id"]

    # Now agent1 can see it.
    assert client.get(f"{LEADS_URL}/{lead['id']}", headers=acme["agent1"]["headers"]).status_code == 200

    with test_engine.connect() as db:
        assert db.execute(text("SELECT COUNT(*) FROM audit_logs WHERE action = 'ASSIGN'")).scalar() == 1


def test_sales_agent_cannot_assign(client, acme):
    lead = make_lead(client, acme["agent1"]["headers"])
    response = client.patch(f"{LEADS_URL}/{lead['id']}/assign", headers=acme["agent1"]["headers"],
                            json={"user_id": acme["agent2"]["id"]})
    assert response.status_code == 403


def test_cannot_assign_to_inactive_or_missing_user(client, acme):
    headers = acme["admin"]["headers"]
    lead = make_lead(client, headers)
    client.patch(f"/api/v1/users/{acme['agent2']['id']}", headers=headers, json={"status": "INACTIVE"})

    url = f"{LEADS_URL}/{lead['id']}/assign"
    assert client.patch(url, headers=headers, json={"user_id": acme["agent2"]["id"]}).status_code == 422
    assert client.patch(url, headers=headers, json={"user_id": 999999}).status_code == 422


def test_assign_missing_lead_returns_404(client, acme):
    response = client.patch(f"{LEADS_URL}/999999/assign", headers=acme["admin"]["headers"],
                            json={"user_id": acme["agent1"]["id"]})
    assert response.status_code == 404


# ---------- Notes ----------

def test_add_and_list_notes(client, acme):
    lead = make_lead(client, acme["agent1"]["headers"])
    url = f"{LEADS_URL}/{lead['id']}/notes"

    response = client.post(url, headers=acme["agent1"]["headers"], json={"content": "Called, very interested."})
    assert response.status_code == 201
    assert response.json()["user_id"] == acme["agent1"]["id"]

    response = client.get(url, headers=acme["manager"]["headers"])
    assert [note["content"] for note in response.json()["data"]] == ["Called, very interested."]

    # agent2 cannot see agent1's lead, so also not its notes.
    assert client.get(url, headers=acme["agent2"]["headers"]).status_code == 404


def test_empty_note_returns_422(client, acme):
    lead = make_lead(client, acme["admin"]["headers"])
    response = client.post(f"{LEADS_URL}/{lead['id']}/notes", headers=acme["admin"]["headers"],
                           json={"content": "   "})
    assert response.status_code == 422


# ---------- Plan limit ----------

def test_free_plan_allows_only_100_leads(client, test_engine):
    registered = register_company(client, email="boss@small.com")
    headers = login(client, "boss@small.com")

    # Insert 100 leads directly in the database to keep the test fast.
    with test_engine.begin() as db:
        for number in range(100):
            db.execute(text("INSERT INTO leads (company_id, first_name, last_name) VALUES (:c, 'Lead', :n)"),
                       {"c": registered["company_id"], "n": str(number)})

    response = client.post(LEADS_URL, headers=headers, json={"first_name": "One", "last_name": "Toomany"})
    assert response.status_code == 403
    assert "FREE plan allows 100 leads" in response.json()["detail"]
