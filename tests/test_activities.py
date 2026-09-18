ACTIVITIES_URL = "/api/v1/activities"


def make_activity(client, headers, **fields):
    data = {"type": "CALL", "title": "Intro call"}
    data.update(fields)
    response = client.post(ACTIVITIES_URL, headers=headers, json=data)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_update_and_complete_activity(client, acme):
    headers = acme["agent1"]["headers"]
    lead = client.post("/api/v1/leads", headers=headers, json={"first_name": "L", "last_name": "D"}).json()

    activity = make_activity(client, headers, lead_id=lead["id"], due_at="2026-10-01T09:00:00Z")
    assert activity["user_id"] == acme["agent1"]["id"]
    assert activity["lead_id"] == lead["id"]

    response = client.patch(f"{ACTIVITIES_URL}/{activity['id']}", headers=headers,
                            json={"completed_at": "2026-10-01T09:30:00Z"})
    assert response.status_code == 200
    assert response.json()["completed_at"].startswith("2026-10-01T09:30")


def test_due_at_with_time_zone_is_saved_in_utc(client, acme):
    activity = make_activity(client, acme["admin"]["headers"], due_at="2026-10-01T12:00:00+02:00")
    assert activity["due_at"].startswith("2026-10-01T10:00")


def test_user_id_cannot_be_chosen(client, acme):
    response = client.post(ACTIVITIES_URL, headers=acme["agent1"]["headers"],
                           json={"type": "CALL", "title": "x", "user_id": acme["agent2"]["id"]})
    assert response.status_code == 422


def test_agent_sees_only_own_activities_manager_sees_all(client, acme):
    make_activity(client, acme["agent1"]["headers"], title="Agent one call")
    make_activity(client, acme["agent2"]["headers"], title="Agent two call")

    response = client.get(ACTIVITIES_URL, headers=acme["agent1"]["headers"])
    assert [activity["title"] for activity in response.json()["data"]] == ["Agent one call"]
    assert client.get(ACTIVITIES_URL, headers=acme["manager"]["headers"]).json()["meta"]["total"] == 2


def test_activity_cannot_link_to_lead_the_agent_cannot_see(client, acme):
    lead = client.post("/api/v1/leads", headers=acme["agent2"]["headers"],
                       json={"first_name": "L", "last_name": "D"}).json()
    response = client.post(ACTIVITIES_URL, headers=acme["agent1"]["headers"],
                           json={"type": "CALL", "title": "x", "lead_id": lead["id"]})
    assert response.status_code == 422


def test_activities_are_isolated_between_companies(client, acme, globex):
    activity = make_activity(client, acme["admin"]["headers"])
    url = f"{ACTIVITIES_URL}/{activity['id']}"

    assert client.get(url, headers=globex["admin"]["headers"]).status_code == 404
    assert client.patch(url, headers=globex["admin"]["headers"], json={"title": "Hacked"}).status_code == 404
    assert client.get(ACTIVITIES_URL, headers=globex["admin"]["headers"]).json()["meta"]["total"] == 0


def test_filter_by_completed(client, acme):
    headers = acme["admin"]["headers"]
    make_activity(client, headers, title="Done", completed_at="2026-09-01T10:00:00Z")
    make_activity(client, headers, title="Open")

    response = client.get(ACTIVITIES_URL, headers=headers, params={"completed": "false"})
    assert [activity["title"] for activity in response.json()["data"]] == ["Open"]
