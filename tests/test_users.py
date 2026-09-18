from helpers import PASSWORD

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


def test_admin_cannot_demote_themselves(client, acme):
    response = client.patch(f"{USERS_URL}/{acme['admin']['id']}",
                            headers=acme["admin"]["headers"], json={"role": "SALES_AGENT"})
    assert response.status_code == 403


# ---------- Update and delete ----------

def test_deactivated_user_is_logged_out(client, acme):
    response = client.patch(f"{USERS_URL}/{acme['agent1']['id']}",
                            headers=acme["admin"]["headers"], json={"status": "INACTIVE"})
    assert response.status_code == 200

    assert client.get("/api/v1/auth/me", headers=acme["agent1"]["headers"]).status_code == 401
    bad_login = client.post("/api/v1/auth/login", json={"email": "agent1@acme.com", "password": PASSWORD})
    assert bad_login.status_code == 401


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
