from helpers import PASSWORD, create_user, login, register_company

USERS_URL = "/api/v1/users"


def new_user_data(email="new@acme.com", role="SALES_AGENT"):
    return {"name": "New Person", "email": email, "password": PASSWORD, "role": role}


# ---------- Who can do what ----------

def test_admin_can_create_a_user(client, acme):
    response = client.post(USERS_URL, headers=acme["admin"]["headers"], json=new_user_data())

    assert response.status_code == 201
    assert response.json()["role"] == "SALES_AGENT"
    assert response.json()["company_id"] == acme["company_id"]
    assert "password" not in response.text


def test_manager_cannot_create_a_user(client, acme):
    response = client.post(USERS_URL, headers=acme["manager"]["headers"], json=new_user_data())
    assert response.status_code == 403


def test_sales_agent_cannot_list_users(client, acme):
    assert client.get(USERS_URL, headers=acme["agent1"]["headers"]).status_code == 403


def test_manager_can_list_users(client, acme):
    response = client.get(USERS_URL, headers=acme["manager"]["headers"])
    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 4


def test_sales_agent_can_see_only_themselves(client, acme):
    headers = acme["agent1"]["headers"]
    assert client.get(f"{USERS_URL}/{acme['agent1']['id']}", headers=headers).status_code == 200
    assert client.get(f"{USERS_URL}/{acme['agent2']['id']}", headers=headers).status_code == 403


def test_no_token_returns_401(client):
    assert client.get(USERS_URL).status_code == 401


# ---------- No role escalation, no mass assignment ----------

def test_cannot_create_an_admin(client, acme):
    response = client.post(USERS_URL, headers=acme["admin"]["headers"], json=new_user_data(role="ADMIN"))
    assert response.status_code == 422


def test_cannot_promote_a_user_to_admin(client, acme):
    response = client.patch(f"{USERS_URL}/{acme['agent1']['id']}",
                            headers=acme["admin"]["headers"], json={"role": "ADMIN"})
    assert response.status_code == 422


def test_cannot_change_company_id(client, acme, globex):
    response = client.patch(f"{USERS_URL}/{acme['agent1']['id']}",
                            headers=acme["admin"]["headers"], json={"company_id": globex["company_id"]})
    assert response.status_code == 422


def test_cannot_send_company_id_when_creating(client, acme, globex):
    data = new_user_data()
    data["company_id"] = globex["company_id"]
    response = client.post(USERS_URL, headers=acme["admin"]["headers"], json=data)
    assert response.status_code == 422


def test_admin_cannot_demote_themselves(client, acme):
    response = client.patch(f"{USERS_URL}/{acme['admin']['id']}",
                            headers=acme["admin"]["headers"], json={"role": "SALES_AGENT"})
    assert response.status_code == 403


def test_admin_cannot_delete_themselves(client, acme):
    response = client.delete(f"{USERS_URL}/{acme['admin']['id']}", headers=acme["admin"]["headers"])
    assert response.status_code == 403


# ---------- Update and delete ----------

def test_admin_can_change_role_and_name(client, acme):
    response = client.patch(f"{USERS_URL}/{acme['agent1']['id']}", headers=acme["admin"]["headers"],
                            json={"role": "MANAGER", "name": "Promoted Person"})
    assert response.status_code == 200
    assert response.json()["role"] == "MANAGER"
    assert response.json()["name"] == "Promoted Person"


def test_deactivated_user_is_logged_out(client, acme):
    response = client.patch(f"{USERS_URL}/{acme['agent1']['id']}",
                            headers=acme["admin"]["headers"], json={"status": "INACTIVE"})
    assert response.status_code == 200

    assert client.get("/api/v1/auth/me", headers=acme["agent1"]["headers"]).status_code == 401
    bad_login = client.post("/api/v1/auth/login", json={"email": "agent1@acme.com", "password": PASSWORD})
    assert bad_login.status_code == 401


def test_deleted_user_disappears_and_cannot_log_in(client, acme):
    url = f"{USERS_URL}/{acme['agent2']['id']}"
    assert client.delete(url, headers=acme["admin"]["headers"]).status_code == 204

    assert client.get(url, headers=acme["admin"]["headers"]).status_code == 404
    assert client.get("/api/v1/auth/me", headers=acme["agent2"]["headers"]).status_code == 401


def test_duplicate_email_returns_409(client, acme):
    response = client.post(USERS_URL, headers=acme["admin"]["headers"],
                           json=new_user_data(email="agent1@acme.com"))
    assert response.status_code == 409


# ---------- Tenant isolation ----------

def test_cannot_see_users_of_another_company(client, acme, globex):
    url = f"{USERS_URL}/{globex['agent1']['id']}"
    assert client.get(url, headers=acme["admin"]["headers"]).status_code == 404


def test_cannot_update_or_delete_users_of_another_company(client, acme, globex):
    url = f"{USERS_URL}/{globex['agent1']['id']}"
    headers = acme["admin"]["headers"]

    assert client.patch(url, headers=headers, json={"name": "Hacked"}).status_code == 404
    assert client.delete(url, headers=headers).status_code == 404

    # Globex's user is unchanged.
    response = client.get(url, headers=globex["admin"]["headers"])
    assert response.json()["name"] != "Hacked"


def test_user_list_only_shows_own_company(client, acme, globex):
    response = client.get(USERS_URL, headers=acme["admin"]["headers"], params={"per_page": 100})
    emails = [row["email"] for row in response.json()["data"]]
    assert all(email.endswith("@acme.com") for email in emails)


# ---------- Plan limit ----------

def test_free_plan_allows_only_3_users(client):
    register_company(client, email="boss@small.com")
    headers = login(client, "boss@small.com")

    create_user(client, headers, "one@small.com", "SALES_AGENT")
    create_user(client, headers, "two@small.com", "SALES_AGENT")

    response = client.post(USERS_URL, headers=headers, json=new_user_data(email="three@small.com"))
    assert response.status_code == 403
    assert "FREE plan allows 3 users" in response.json()["detail"]


# ---------- List filters ----------

def test_list_users_with_filters_and_pagination(client, acme):
    headers = acme["admin"]["headers"]

    response = client.get(USERS_URL, headers=headers, params={"role": "SALES_AGENT"})
    assert response.json()["meta"]["total"] == 2

    response = client.get(USERS_URL, headers=headers, params={"search": "manager"})
    assert [user["email"] for user in response.json()["data"]] == ["manager@acme.com"]

    response = client.get(USERS_URL, headers=headers, params={"per_page": 3, "page": 2})
    assert len(response.json()["data"]) == 1
    assert response.json()["meta"]["total_pages"] == 2

    assert client.get(USERS_URL, headers=headers, params={"per_page": 1000}).status_code == 422
