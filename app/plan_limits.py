"""Checks the company's plan before creating a new user or lead."""
from fastapi import HTTPException
from sqlalchemy import text


def get_company_plan_and_lock(db, company_id):
    """Return the company's plan (name, user_limit, lead_limit).

    FOR UPDATE locks the company's subscription row until the transaction ends.
    If two requests try to add a lead at the same time, the second one waits here
    until the first is finished. So the company can never go over its limit.
    """
    subscription = db.execute(
        text("SELECT plan_id, status FROM subscriptions WHERE company_id = :company_id FOR UPDATE"),
        {"company_id": company_id},
    ).mappings().first()

    if subscription is None or subscription["status"] != "ACTIVE":
        raise HTTPException(403, "Your company does not have an active subscription.")

    return db.execute(
        text("SELECT name, user_limit, lead_limit FROM plans WHERE id = :id"),
        {"id": subscription["plan_id"]},
    ).mappings().one()


def check_user_limit(db, company_id):
    plan = get_company_plan_and_lock(db, company_id)
    limit = plan["user_limit"]

    # None means unlimited (ENTERPRISE).
    if limit is None:
        return

    user_count = db.execute(
        text("SELECT COUNT(*) FROM users WHERE company_id = :company_id AND deleted_at IS NULL"),
        {"company_id": company_id},
    ).scalar()

    if user_count >= limit:
        raise HTTPException(403, f"Your {plan['name']} plan allows {limit} users. Upgrade your plan to add more.")


def check_lead_limit(db, company_id):
    plan = get_company_plan_and_lock(db, company_id)
    limit = plan["lead_limit"]

    if limit is None:
        return

    lead_count = db.execute(
        text("SELECT COUNT(*) FROM leads WHERE company_id = :company_id AND deleted_at IS NULL"),
        {"company_id": company_id},
    ).scalar()

    if lead_count >= limit:
        raise HTTPException(403, f"Your {plan['name']} plan allows {limit} leads. Upgrade your plan to add more.")
