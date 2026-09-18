"""The logged-in user's own company, its subscription and the available plans.

There is no company id in these URLs. The company always comes from the login token,
so a user can only ever see or change their own company.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text

from app.audit import save_audit_log
from app.database import get_engine
from app.plan_limits import count_leads, count_users, get_company_plan
from app.schemas.company import (
    CompanyResponse, CompanyUpdate, PlanResponse, SubscriptionResponse, SubscriptionUpdate,
)
from app.security import ADMIN, MANAGER, allow_roles, get_current_user

router = APIRouter(prefix="/api/v1", tags=["Company & Subscription"])

COMPANY_COLUMNS = "id, name, email, phone, website, status, created_at, updated_at"


def get_company(db, company_id):
    return db.execute(
        text(f"SELECT {COMPANY_COLUMNS} FROM companies WHERE id = :id"), {"id": company_id}
    ).mappings().one()


@router.get("/company", response_model=CompanyResponse)
def show_company(user=Depends(get_current_user), engine=Depends(get_engine)):
    with engine.connect() as db:
        return get_company(db, user["company_id"])


@router.patch("/company", response_model=CompanyResponse)
def update_company(data: CompanyUpdate, request: Request,
                   user=Depends(allow_roles(ADMIN)), engine=Depends(get_engine)):
    # exclude_unset=True: only the fields the client actually sent.
    changes = data.model_dump(exclude_unset=True)

    with engine.begin() as db:
        old_company = get_company(db, user["company_id"])

        if changes:
            # Builds for example: UPDATE companies SET name = :name, phone = :phone WHERE id = :id
            set_sql = ", ".join(f"{column} = :{column}" for column in changes)
            params = dict(changes)
            params["id"] = user["company_id"]
            db.execute(text(f"UPDATE companies SET {set_sql} WHERE id = :id"), params)

        new_company = get_company(db, user["company_id"])
        save_audit_log(db, user, "UPDATE", "company", user["company_id"], request,
                       old_values=old_company, new_values=new_company)

    return new_company


@router.get("/plans", response_model=list[PlanResponse])
def list_plans(user=Depends(get_current_user), engine=Depends(get_engine)):
    with engine.connect() as db:
        return db.execute(text("SELECT name, user_limit, lead_limit FROM plans ORDER BY id")).mappings().all()


@router.get("/subscription", response_model=SubscriptionResponse)
def show_subscription(user=Depends(allow_roles(ADMIN, MANAGER)), engine=Depends(get_engine)):
    with engine.connect() as db:
        plan = get_company_plan(db, user["company_id"])
        return {
            "plan": plan,
            "status": "ACTIVE",
            "users_used": count_users(db, user["company_id"]),
            "leads_used": count_leads(db, user["company_id"]),
        }


@router.patch("/subscription", response_model=SubscriptionResponse)
def change_plan(data: SubscriptionUpdate, request: Request,
                user=Depends(allow_roles(ADMIN)), engine=Depends(get_engine)):
    """Switch the company to another plan. (No real payment provider, as the brief allows.)"""
    company_id = user["company_id"]

    with engine.begin() as db:
        old_plan = get_company_plan(db, company_id, lock=True)
        new_plan = db.execute(
            text("SELECT id, name, user_limit, lead_limit FROM plans WHERE name = :name"),
            {"name": data.plan},
        ).mappings().one()

        users_used = count_users(db, company_id)
        leads_used = count_leads(db, company_id)

        # Do not allow a downgrade if the company already has more than the new plan allows.
        if new_plan["user_limit"] is not None and users_used > new_plan["user_limit"]:
            raise HTTPException(409, f"You have {users_used} users, but the {data.plan} plan allows only "
                                     f"{new_plan['user_limit']}. Remove some users first.")
        if new_plan["lead_limit"] is not None and leads_used > new_plan["lead_limit"]:
            raise HTTPException(409, f"You have {leads_used} leads, but the {data.plan} plan allows only "
                                     f"{new_plan['lead_limit']}. Remove some leads first.")

        db.execute(
            text("UPDATE subscriptions SET plan_id = :plan_id WHERE company_id = :company_id"),
            {"plan_id": new_plan["id"], "company_id": company_id},
        )
        save_audit_log(db, user, "UPDATE", "subscription", company_id, request,
                       old_values={"plan": old_plan["name"]}, new_values={"plan": new_plan["name"]})

    return {
        "plan": new_plan,
        "status": "ACTIVE",
        "users_used": users_used,
        "leads_used": leads_used,
    }
