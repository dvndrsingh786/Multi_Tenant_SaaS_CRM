"""Functions that load ONE record by its id.

This file is the heart of tenant isolation for single records:
- every query filters by the logged-in user's company_id,
- a SALES_AGENT only gets records they own,
- anything else is reported as 404 "not found".

We answer 404 (not 403) for other companies' records, so an attacker cannot even
find out that a record with that id exists.
"""
from fastapi import HTTPException
from sqlalchemy import text

from app.security import SALES_AGENT


def find_record(db, user, table, record_id, owner_column, not_found_message,
                soft_delete=True, lock=False):
    # table and owner_column always come from the small functions below, never from the client.
    sql = f"SELECT * FROM {table} WHERE id = :id AND company_id = :company_id"
    params = {"id": record_id, "company_id": user["company_id"]}

    if soft_delete:
        sql += " AND deleted_at IS NULL"

    if user["role"] == SALES_AGENT:
        sql += f" AND {owner_column} = :user_id"
        params["user_id"] = user["id"]

    # FOR UPDATE locks the row until the transaction ends (used when we are about to change it).
    if lock:
        sql += " FOR UPDATE"

    record = db.execute(text(sql), params).mappings().first()
    if record is None:
        raise HTTPException(404, not_found_message)
    return record


def find_lead(db, user, lead_id, lock=False):
    return find_record(db, user, "leads", lead_id, "assigned_to", "Lead not found.", lock=lock)


def find_customer(db, user, customer_id, lock=False):
    return find_record(db, user, "customers", customer_id, "assigned_to", "Customer not found.", lock=lock)


def find_contact(db, user, contact_id, lock=False):
    return find_record(db, user, "contacts", contact_id, "owner_id", "Contact not found.", lock=lock)


def find_deal(db, user, deal_id, lock=False):
    return find_record(db, user, "deals", deal_id, "assigned_to", "Deal not found.", lock=lock)


def find_activity(db, user, activity_id, lock=False):
    # Activities have no deleted_at column (the brief has no DELETE endpoint for them).
    return find_record(db, user, "activities", activity_id, "user_id", "Activity not found.",
                       soft_delete=False, lock=lock)


def check_linked_records(db, user, lead_id=None, customer_id=None, deal_id=None):
    """When a deal or activity points to a lead/customer/deal, that record must be one
    the user can see. Otherwise we answer 422 (the request data is invalid)."""
    checks = [
        ("lead_id", lead_id, find_lead),
        ("customer_id", customer_id, find_customer),
        ("deal_id", deal_id, find_deal),
    ]
    for field_name, record_id, find_function in checks:
        if record_id is None:
            continue
        try:
            find_function(db, user, record_id)
        except HTTPException:
            raise HTTPException(422, f"{field_name}: no such record in your company.")
