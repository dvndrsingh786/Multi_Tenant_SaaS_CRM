DEALS_URL = "/api/v1/deals"


def make_deal(client, headers, **fields):
    data = {"title": "Website redesign", "value": 5000}
    data.update(fields)
    response = client.post(DEALS_URL, headers=headers, json=data)
    assert response.status_code == 201, response.text
    return response.json()


def make_customer(client, headers):
    response = client.post("/api/v1/customers", headers=headers, json={"first_name": "C", "last_name": "D"})
    return response.json()


def test_deal_crud_and_stage(client, acme):
    headers = acme["manager"]["headers"]
    customer = make_customer(client, acme["admin"]["headers"])
    deal = make_deal(client, headers, customer_id=customer["id"], expected_close_date="2026-12-31")
    url = f"{DEALS_URL}/{deal['id']}"

    assert deal["stage"] == "NEW"
    assert deal["customer_id"] == customer["id"]

    response = client.patch(url, headers=headers, json={"value": 7500.25, "title": "Bigger redesign"})
    assert response.json()["value"] == 7500.25

    response = client.patch(f"{url}/stage", headers=headers, json={"stage": "PROPOSAL"})
    assert response.status_code == 200
    assert response.json()["stage"] == "PROPOSAL"

    assert client.delete(url, headers=headers).status_code == 204
    assert client.get(url, headers=headers).status_code == 404


def test_invalid_stage_returns_422(client, acme):
    deal = make_deal(client, acme["admin"]["headers"])
    response = client.patch(f"{DEALS_URL}/{deal['id']}/stage", headers=acme["admin"]["headers"],
                            json={"stage": "ALMOST"})
    assert response.status_code == 422


def test_stage_cannot_be_changed_with_normal_patch(client, acme):
    deal = make_deal(client, acme["admin"]["headers"])
    response = client.patch(f"{DEALS_URL}/{deal['id']}", headers=acme["admin"]["headers"], json={"stage": "WON"})
    assert response.status_code == 422


def test_agent_manages_only_their_own_deals(client, acme):
    own = make_deal(client, acme["agent1"]["headers"], title="Mine")
    other = make_deal(client, acme["agent2"]["headers"], title="Theirs")
    headers = acme["agent1"]["headers"]

    assert own["assigned_to"] == acme["agent1"]["id"]
    assert [deal["title"] for deal in client.get(DEALS_URL, headers=headers).json()["data"]] == ["Mine"]
    assert client.patch(f"{DEALS_URL}/{other['id']}/stage", headers=headers,
                        json={"stage": "WON"}).status_code == 404
    assert client.patch(f"{DEALS_URL}/{own['id']}/stage", headers=headers,
                        json={"stage": "WON"}).status_code == 200


def test_agent_cannot_hand_deal_to_someone_else(client, acme):
    deal = make_deal(client, acme["agent1"]["headers"])
    response = client.patch(f"{DEALS_URL}/{deal['id']}", headers=acme["agent1"]["headers"],
                            json={"assigned_to": acme["agent2"]["id"]})
    assert response.status_code == 403


def test_deals_are_isolated_between_companies(client, acme, globex):
    deal = make_deal(client, acme["admin"]["headers"])
    url = f"{DEALS_URL}/{deal['id']}"
    headers = globex["admin"]["headers"]

    assert client.get(url, headers=headers).status_code == 404
    assert client.patch(url, headers=headers, json={"title": "Hacked"}).status_code == 404
    assert client.patch(f"{url}/stage", headers=headers, json={"stage": "LOST"}).status_code == 404
    assert client.delete(url, headers=headers).status_code == 404


def test_deal_cannot_link_to_other_company_customer(client, acme, globex):
    their_customer = make_customer(client, globex["admin"]["headers"])
    response = client.post(DEALS_URL, headers=acme["admin"]["headers"],
                           json={"title": "Sneaky", "customer_id": their_customer["id"]})
    assert response.status_code == 422


def test_deal_list_filters(client, acme):
    headers = acme["admin"]["headers"]
    make_deal(client, headers, title="Small", value=100, stage="WON")
    make_deal(client, headers, title="Large", value=9000, stage="WON")
    make_deal(client, headers, title="Other", value=500, stage="NEW")

    response = client.get(DEALS_URL, headers=headers, params={"stage": "WON", "sort_by": "value",
                                                               "sort_order": "asc"})
    assert [deal["title"] for deal in response.json()["data"]] == ["Small", "Large"]
