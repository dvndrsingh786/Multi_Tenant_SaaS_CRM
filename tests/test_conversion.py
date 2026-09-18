import threading
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError

from app.main import app


def make_lead(client, headers, **fields):
    data = {"first_name": "Jane", "last_name": "Doe", "email": "jane@example.com",
            "phone": "0123", "company_name": "Doe Ltd"}
    data.update(fields)
    response = client.post("/api/v1/leads", headers=headers, json=data)
    assert response.status_code == 201, response.text
    return response.json()


def count_rows(test_engine, sql, params=None):
    with test_engine.connect() as db:
        return db.execute(text(sql), params or {}).scalar()


def test_convert_creates_customer_activity_and_audit_log(client, acme, test_engine):
    lead = make_lead(client, acme["admin"]["headers"], assigned_to=acme["agent1"]["id"])

    response = client.post(f"/api/v1/leads/{lead['id']}/convert", headers=acme["admin"]["headers"])

    assert response.status_code == 201
    customer = response.json()
    # Lead information is kept on the customer.
    assert customer["lead_id"] == lead["id"]
    assert customer["first_name"] == "Jane"
    assert customer["email"] == "jane@example.com"
    assert customer["company_name"] == "Doe Ltd"
    assert customer["assigned_to"] == acme["agent1"]["id"]

    # The lead is marked as converted.
    lead_after = client.get(f"/api/v1/leads/{lead['id']}", headers=acme["admin"]["headers"]).json()
    assert lead_after["converted_at"] is not None
    assert lead_after["status"] == "WON"

    assert count_rows(test_engine, "SELECT COUNT(*) FROM activities WHERE customer_id = :id",
                      {"id": customer["id"]}) == 1
    assert count_rows(test_engine, "SELECT COUNT(*) FROM audit_logs WHERE action = 'CONVERT'") == 1


def test_converting_twice_returns_409(client, acme, test_engine):
    lead = make_lead(client, acme["admin"]["headers"])
    url = f"/api/v1/leads/{lead['id']}/convert"

    assert client.post(url, headers=acme["admin"]["headers"]).status_code == 201
    assert client.post(url, headers=acme["admin"]["headers"]).status_code == 409
    assert count_rows(test_engine, "SELECT COUNT(*) FROM customers") == 1


def test_concurrent_conversions_create_only_one_customer(client, acme, test_engine):
    """Send 5 convert requests at the same moment. Exactly one may succeed."""
    lead = make_lead(client, acme["admin"]["headers"])
    url = f"/api/v1/leads/{lead['id']}/convert"
    headers = acme["admin"]["headers"]

    # The barrier makes all 5 threads wait, then start at the same time.
    start_together = threading.Barrier(5)

    def convert():
        start_together.wait()
        return client.post(url, headers=headers).status_code

    with ThreadPoolExecutor(max_workers=5) as pool:
        status_codes = list(pool.map(lambda _: convert(), range(5)))

    assert sorted(status_codes) == [201, 409, 409, 409, 409]
    assert count_rows(test_engine, "SELECT COUNT(*) FROM customers WHERE lead_id = :id", {"id": lead["id"]}) == 1


def test_second_request_waits_for_the_lock_then_gets_409(client, acme, test_engine):
    """Show step by step what FOR UPDATE does.

    We lock the lead row ourselves, start a convert request (it has to wait),
    then finish "our" conversion. The waiting request must then answer 409.
    """
    lead = make_lead(client, acme["admin"]["headers"])
    url = f"/api/v1/leads/{lead['id']}/convert"
    result = {}

    with test_engine.connect() as db:
        transaction = db.begin()
        db.execute(text("SELECT id FROM leads WHERE id = :id FOR UPDATE"), {"id": lead["id"]})

        request_thread = threading.Thread(
            target=lambda: result.update(status=client.post(url, headers=acme["admin"]["headers"]).status_code)
        )
        request_thread.start()
        time.sleep(0.5)
        assert "status" not in result  # still waiting for our lock

        db.execute(text("UPDATE leads SET converted_at = UTC_TIMESTAMP() WHERE id = :id"), {"id": lead["id"]})
        transaction.commit()

    request_thread.join(timeout=10)
    assert result["status"] == 409


def test_unique_key_is_a_safety_net(client, acme, test_engine):
    """Even if the lead is not marked as converted, MySQL refuses a second customer for it."""
    lead = make_lead(client, acme["admin"]["headers"])
    with test_engine.begin() as db:
        db.execute(text("INSERT INTO customers (company_id, lead_id, first_name, last_name) "
                        "VALUES (:company_id, :lead_id, 'Jane', 'Doe')"),
                   {"company_id": acme["company_id"], "lead_id": lead["id"]})

    response = client.post(f"/api/v1/leads/{lead['id']}/convert", headers=acme["admin"]["headers"])
    assert response.status_code == 409
    assert count_rows(test_engine, "SELECT COUNT(*) FROM customers") == 1


def test_failure_in_the_middle_undoes_everything(acme, test_engine):
    """If writing the audit log fails, the customer must not exist and the lead must not be converted."""
    # A client that returns the 500 response instead of raising the error in the test.
    safe_client = TestClient(app, raise_server_exceptions=False)
    lead = make_lead(safe_client, acme["admin"]["headers"])

    def fail_on_audit_log(connection, cursor, statement, parameters, context, executemany):
        if "INSERT INTO audit_logs" in statement:
            raise OperationalError(statement, parameters, Exception("simulated failure"))

    event.listen(test_engine, "before_cursor_execute", fail_on_audit_log)
    try:
        response = safe_client.post(f"/api/v1/leads/{lead['id']}/convert", headers=acme["admin"]["headers"])
    finally:
        event.remove(test_engine, "before_cursor_execute", fail_on_audit_log)

    assert response.status_code == 500
    assert "simulated" not in response.text  # no internal details leak out
    assert count_rows(test_engine, "SELECT COUNT(*) FROM customers") == 0
    assert count_rows(test_engine, "SELECT converted_at FROM leads WHERE id = :id", {"id": lead["id"]}) is None
    assert count_rows(test_engine, "SELECT COUNT(*) FROM activities") == 0


def test_other_company_cannot_convert(client, acme, globex, test_engine):
    lead = make_lead(client, acme["admin"]["headers"])
    response = client.post(f"/api/v1/leads/{lead['id']}/convert", headers=globex["admin"]["headers"])
    assert response.status_code == 404
    assert count_rows(test_engine, "SELECT COUNT(*) FROM customers") == 0


def test_sales_agent_can_convert_only_their_own_lead(client, acme):
    own = make_lead(client, acme["agent1"]["headers"])
    other = make_lead(client, acme["agent2"]["headers"])
    headers = acme["agent1"]["headers"]

    assert client.post(f"/api/v1/leads/{other['id']}/convert", headers=headers).status_code == 404
    assert client.post(f"/api/v1/leads/{own['id']}/convert", headers=headers).status_code == 201
