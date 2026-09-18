from sqlalchemy import text

from helpers import login
from seed import seed


def count(test_engine, sql):
    with test_engine.connect() as db:
        return db.execute(text(sql)).scalar()


def test_seed_creates_two_full_companies(client, test_engine):
    seed(test_engine)

    assert count(test_engine, "SELECT COUNT(*) FROM companies") == 2
    assert count(test_engine, "SELECT COUNT(*) FROM users") == 8
    assert count(test_engine, "SELECT COUNT(*) FROM leads") == 50
    assert count(test_engine, "SELECT MIN(total) FROM (SELECT COUNT(*) AS total FROM customers "
                              "GROUP BY company_id) AS per_company") >= 5
    assert count(test_engine, "SELECT COUNT(*) FROM deals") == 20

    # Running it again does not create duplicates.
    seed(test_engine)
    assert count(test_engine, "SELECT COUNT(*) FROM companies") == 2


def test_seeded_users_can_log_in_and_only_see_their_company(client, test_engine):
    seed(test_engine)

    acme_headers = login(client, "admin@acme.example")
    globex_headers = login(client, "admin@globex.example")

    acme_leads = client.get("/api/v1/leads", headers=acme_headers, params={"per_page": 100}).json()
    globex_leads = client.get("/api/v1/leads", headers=globex_headers, params={"per_page": 100}).json()

    assert acme_leads["meta"]["total"] == 25
    assert globex_leads["meta"]["total"] == 25
    acme_ids = {lead["id"] for lead in acme_leads["data"]}
    globex_ids = {lead["id"] for lead in globex_leads["data"]}
    assert acme_ids.isdisjoint(globex_ids)
