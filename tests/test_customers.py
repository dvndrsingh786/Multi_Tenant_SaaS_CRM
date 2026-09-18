CUSTOMERS_URL = "/api/v1/customers"


def make_customer(client, headers, **fields):
    data = {"first_name": "Carl", "last_name": "Customer"}
    data.update(fields)
    response = client.post(CUSTOMERS_URL, headers=headers, json=data)
    assert response.status_code == 201, response.text
    return response.json()


def test_admin_customer_crud(client, acme):
    headers = acme["admin"]["headers"]
    customer = make_customer(client, headers, email="carl@example.com")
    url = f"{CUSTOMERS_URL}/{customer['id']}"

    assert client.get(url, headers=headers).json()["email"] == "carl@example.com"

    response = client.patch(url, headers=headers, json={"status": "INACTIVE"})
    assert response.status_code == 200
    assert response.json()["status"] == "INACTIVE"

    assert client.delete(url, headers=headers).status_code == 204
    assert client.get(url, headers=headers).status_code == 404


def test_manager_and_agent_can_only_view(client, acme):
    customer = make_customer(client, acme["admin"]["headers"], assigned_to=acme["agent1"]["id"])
    url = f"{CUSTOMERS_URL}/{customer['id']}"

    for role in ["manager", "agent1"]:
        headers = acme[role]["headers"]
        assert client.get(url, headers=headers).status_code == 200
        assert client.patch(url, headers=headers, json={"status": "INACTIVE"}).status_code == 403
        assert client.delete(url, headers=headers).status_code == 403
        assert client.post(CUSTOMERS_URL, headers=headers,
                           json={"first_name": "A", "last_name": "B"}).status_code == 403


def test_agent_only_sees_assigned_customers(client, acme):
    make_customer(client, acme["admin"]["headers"], first_name="Mine", assigned_to=acme["agent1"]["id"])
    other = make_customer(client, acme["admin"]["headers"], first_name="NotMine", assigned_to=acme["agent2"]["id"])

    response = client.get(CUSTOMERS_URL, headers=acme["agent1"]["headers"])
    assert [customer["first_name"] for customer in response.json()["data"]] == ["Mine"]

    assert client.get(f"{CUSTOMERS_URL}/{other['id']}", headers=acme["agent1"]["headers"]).status_code == 404


def test_customers_are_isolated_between_companies(client, acme, globex):
    customer = make_customer(client, acme["admin"]["headers"], first_name="AcmeOnly")
    url = f"{CUSTOMERS_URL}/{customer['id']}"
    headers = globex["admin"]["headers"]

    assert client.get(url, headers=headers).status_code == 404
    assert client.patch(url, headers=headers, json={"first_name": "Hacked"}).status_code == 404
    assert client.delete(url, headers=headers).status_code == 404
    assert client.get(CUSTOMERS_URL, headers=headers).json()["meta"]["total"] == 0


def test_cannot_set_lead_id_or_company_id(client, acme, globex):
    response = client.post(CUSTOMERS_URL, headers=acme["admin"]["headers"],
                           json={"first_name": "A", "last_name": "B", "lead_id": 1})
    assert response.status_code == 422

    response = client.post(CUSTOMERS_URL, headers=acme["admin"]["headers"],
                           json={"first_name": "A", "last_name": "B", "company_id": globex["company_id"]})
    assert response.status_code == 422


def test_cannot_assign_customer_to_other_company_user(client, acme, globex):
    response = client.post(CUSTOMERS_URL, headers=acme["admin"]["headers"],
                           json={"first_name": "A", "last_name": "B", "assigned_to": globex["agent1"]["id"]})
    assert response.status_code == 422


def test_customer_search_and_filter(client, acme):
    headers = acme["admin"]["headers"]
    make_customer(client, headers, first_name="Anna", status="ACTIVE")
    make_customer(client, headers, first_name="Anneliese", status="INACTIVE")
    make_customer(client, headers, first_name="Bob")

    response = client.get(CUSTOMERS_URL, headers=headers, params={"search": "ann", "status": "ACTIVE"})
    assert [customer["first_name"] for customer in response.json()["data"]] == ["Anna"]
