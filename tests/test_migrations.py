from sqlalchemy import text

from migrate import run_migrations


def test_all_tables_are_created(test_engine):
    with test_engine.connect() as db:
        tables = set(db.execute(text("SHOW TABLES")).scalars())

    expected = {
        "companies", "users", "plans", "subscriptions", "leads", "contacts", "customers",
        "deals", "activities", "notes", "audit_logs", "auth_tokens", "rate_limits", "notifications",
    }
    assert expected <= tables


def test_plans_have_the_right_limits(test_engine):
    with test_engine.connect() as db:
        rows = db.execute(text("SELECT name, user_limit, lead_limit FROM plans ORDER BY id")).all()

    assert [tuple(row) for row in rows] == [
        ("FREE", 3, 100),
        ("STARTER", 10, 1000),
        ("PRO", 50, 10000),
        ("ENTERPRISE", None, None),
    ]


def test_running_migrations_twice_does_nothing(test_engine):
    # The second run should skip every file instead of failing with "table already exists".
    run_migrations(test_engine)


def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
