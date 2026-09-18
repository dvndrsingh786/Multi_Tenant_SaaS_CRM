from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.jobs import clean_up_expired_rows, send_activity_reminders


def in_minutes(minutes):
    moment = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def add_activity(client, headers, title, **fields):
    data = {"type": "TASK", "title": title}
    data.update(fields)
    response = client.post("/api/v1/activities", headers=headers, json=data)
    assert response.status_code == 201, response.text
    return response.json()


def test_reminders_only_for_unfinished_activities_due_soon(client, acme, test_engine):
    headers = acme["agent1"]["headers"]
    add_activity(client, headers, "Due soon", due_at=in_minutes(30))
    add_activity(client, headers, "Due tomorrow", due_at=in_minutes(60 * 24))
    add_activity(client, headers, "Already late", due_at=in_minutes(-30))
    add_activity(client, headers, "Done already", due_at=in_minutes(20), completed_at=in_minutes(-5))
    add_activity(client, headers, "No due date")

    assert send_activity_reminders(test_engine) == 1

    with test_engine.connect() as db:
        notifications = db.execute(text("SELECT user_id, company_id, message FROM notifications")).mappings().all()
    assert len(notifications) == 1
    assert "Due soon" in notifications[0]["message"]
    # The reminder goes to the activity's owner, inside the owner's company.
    assert notifications[0]["user_id"] == acme["agent1"]["id"]
    assert notifications[0]["company_id"] == acme["company_id"]


def test_running_the_job_twice_does_not_send_twice(client, acme, test_engine):
    add_activity(client, acme["agent1"]["headers"], "Due soon", due_at=in_minutes(10))

    assert send_activity_reminders(test_engine) == 1
    assert send_activity_reminders(test_engine) == 0

    with test_engine.connect() as db:
        assert db.execute(text("SELECT COUNT(*) FROM notifications")).scalar() == 1


def test_clean_up_removes_expired_tokens(client, acme, test_engine):
    with test_engine.begin() as db:
        db.execute(text("UPDATE auth_tokens SET expires_at = DATE_SUB(UTC_TIMESTAMP(), INTERVAL 1 HOUR) "
                        "WHERE user_id = :id"), {"id": acme["agent1"]["id"]})

    clean_up_expired_rows(test_engine)

    with test_engine.connect() as db:
        left = db.execute(text("SELECT COUNT(*) FROM auth_tokens WHERE user_id = :id"),
                          {"id": acme["agent1"]["id"]}).scalar()
    assert left == 0
    # Other users are still logged in.
    assert client.get("/api/v1/auth/me", headers=acme["agent2"]["headers"]).status_code == 200
