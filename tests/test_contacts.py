CONTACTS_URL = "/api/v1/contacts"


def make_contact(client, headers, **fields):
    data = {"first_name": "Cara", "last_name": "Contact"}
    data.update(fields)
    response = client.post(CONTACTS_URL, headers=headers, json=data)
    assert response.status_code == 201, response.text
    return response.json()


def test_contact_crud(client, acme):
    headers = acme["manager"]["headers"]
    contact = make_contact(client, headers, email="cara@example.com", job_title="CTO")
    url = f"{CONTACTS_URL}/{contact['id']}"

    assert contact["owner_id"] == acme["manager"]["id"]  # defaults to the creator
    assert client.get(url, headers=headers).json()["job_title"] == "CTO"

    response = client.patch(url, headers=headers, json={"phone": "0200"})
    assert response.json()["phone"] == "0200"

    assert client.delete(url, headers=headers).status_code == 204
    assert client.get(url, headers=headers).status_code == 404


def test_agent_only_sees_own_contacts(client, acme):
    make_contact(client, acme["agent1"]["headers"], first_name="Mine")
    other = make_contact(client, acme["agent2"]["headers"], first_name="Theirs")

    response = client.get(CONTACTS_URL, headers=acme["agent1"]["headers"])
    assert [contact["first_name"] for contact in response.json()["data"]] == ["Mine"]
    assert client.get(f"{CONTACTS_URL}/{other['id']}", headers=acme["agent1"]["headers"]).status_code == 404

    # The manager sees both.
    assert client.get(CONTACTS_URL, headers=acme["manager"]["headers"]).json()["meta"]["total"] == 2


def test_agent_cannot_give_contact_to_someone_else(client, acme):
    contact = make_contact(client, acme["agent1"]["headers"])
    response = client.patch(f"{CONTACTS_URL}/{contact['id']}", headers=acme["agent1"]["headers"],
                            json={"owner_id": acme["agent2"]["id"]})
    assert response.status_code == 403


def test_contacts_are_isolated_between_companies(client, acme, globex):
    contact = make_contact(client, acme["admin"]["headers"])
    url = f"{CONTACTS_URL}/{contact['id']}"
    headers = globex["admin"]["headers"]

    assert client.get(url, headers=headers).status_code == 404
    assert client.patch(url, headers=headers, json={"first_name": "Hacked"}).status_code == 404
    assert client.delete(url, headers=headers).status_code == 404
    assert client.get(CONTACTS_URL, headers=headers).json()["meta"]["total"] == 0


def test_contact_owner_must_be_in_same_company(client, acme, globex):
    response = client.post(CONTACTS_URL, headers=acme["admin"]["headers"],
                           json={"first_name": "A", "last_name": "B", "owner_id": globex["agent1"]["id"]})
    assert response.status_code == 422
