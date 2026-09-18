"""Leads, lead assignment and lead notes.

Who can see which leads:
- ADMIN and MANAGER: every lead in their company.
- SALES_AGENT: only the leads assigned to them.

Who can do what:
- Everyone can create, update, convert and add notes to the leads they can see.
- ADMIN and MANAGER can assign leads.
- Only ADMIN can delete leads.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.audit import save_audit_log
from app.database import get_engine
from app.plan_limits import check_lead_limit
from app.schemas.customers import CustomerResponse
from app.schemas.leads import (
    AssignRequest, LeadCreate, LeadList, LeadResponse, LeadSource, LeadStatus, LeadUpdate,
    NoteCreate, NoteList, NoteResponse,
)
from app.security import ADMIN, MANAGER, SALES_AGENT, allow_roles, get_current_user
from app.utils import check_user_can_be_assigned, like_pattern, paginate, update_row

router = APIRouter(prefix="/api/v1/leads", tags=["Leads"])


def find_lead(db, user, lead_id, lock=False):
    """Load one lead, but only if this user is allowed to see it. Otherwise 404.

    lock=True adds FOR UPDATE, which locks the row until the transaction ends.
    """
    sql = "SELECT * FROM leads WHERE id = :id AND company_id = :company_id AND deleted_at IS NULL"
    params = {"id": lead_id, "company_id": user["company_id"]}

    if user["role"] == SALES_AGENT:
        sql += " AND assigned_to = :user_id"
        params["user_id"] = user["id"]

    if lock:
        sql += " FOR UPDATE"

    lead = db.execute(text(sql), params).mappings().first()
    if lead is None:
        raise HTTPException(404, "Lead not found.")
    return lead


# ---------- List ----------

@router.get("", response_model=LeadList)
def list_leads(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    status: LeadStatus | None = None,
    source: LeadSource | None = None,
    assigned_to: int | None = None,
    sort_by: Literal["created_at", "updated_at", "first_name", "last_name",
                     "estimated_value", "status"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    user=Depends(get_current_user),
    engine=Depends(get_engine),
):
    # These two rules are ALWAYS added. They keep every user inside their own company.
    conditions = ["company_id = :company_id", "deleted_at IS NULL"]
    params = {"company_id": user["company_id"]}

    if user["role"] == SALES_AGENT:
        conditions.append("assigned_to = :current_user_id")
        params["current_user_id"] = user["id"]

    if search:
        conditions.append("""(first_name LIKE :search OR last_name LIKE :search
                              OR email LIKE :search OR company_name LIKE :search)""")
        params["search"] = like_pattern(search)
    if status:
        conditions.append("status = :status")
        params["status"] = status
    if source:
        conditions.append("source = :source")
        params["source"] = source
    if assigned_to:
        conditions.append("assigned_to = :assigned_to")
        params["assigned_to"] = assigned_to

    where_sql = " AND ".join(conditions)

    # sort_by and sort_order can only be one of the values listed in the Literal above
    # (FastAPI returns 422 for anything else), so it is safe to put them in the SQL.
    # "id" is added as a tie-breaker so the order is always the same.
    order_sql = f"ORDER BY {sort_by} {sort_order}, id {sort_order}"

    with engine.connect() as db:
        return paginate(
            db,
            select_sql=f"SELECT * FROM leads WHERE {where_sql} {order_sql}",
            count_sql=f"SELECT COUNT(*) FROM leads WHERE {where_sql}",
            params=params,
            page=page,
            per_page=per_page,
        )


# ---------- Create, read, update, delete ----------

@router.post("", status_code=201, response_model=LeadResponse)
def create_lead(data: LeadCreate, request: Request,
                user=Depends(get_current_user), engine=Depends(get_engine)):
    lead = data.model_dump()

    # A sales agent's new lead is always assigned to themselves.
    if user["role"] == SALES_AGENT:
        if lead["assigned_to"] not in (None, user["id"]):
            raise HTTPException(403, "Sales agents can only create leads for themselves.")
        lead["assigned_to"] = user["id"]

    lead["company_id"] = user["company_id"]

    with engine.begin() as db:
        check_lead_limit(db, user["company_id"])
        if lead["assigned_to"] is not None:
            check_user_can_be_assigned(db, user["company_id"], lead["assigned_to"])

        result = db.execute(
            text("""
                INSERT INTO leads (company_id, assigned_to, first_name, last_name, email, phone,
                                   company_name, job_title, source, status, estimated_value)
                VALUES (:company_id, :assigned_to, :first_name, :last_name, :email, :phone,
                        :company_name, :job_title, :source, :status, :estimated_value)
            """),
            lead,
        )
        new_lead = find_lead(db, user, result.lastrowid)
        save_audit_log(db, user, "CREATE", "lead", new_lead["id"], request, new_values=new_lead)

    return new_lead


@router.get("/{lead_id}", response_model=LeadResponse)
def show_lead(lead_id: int, user=Depends(get_current_user), engine=Depends(get_engine)):
    with engine.connect() as db:
        return find_lead(db, user, lead_id)


@router.patch("/{lead_id}", response_model=LeadResponse)
def update_lead(lead_id: int, data: LeadUpdate, request: Request,
                user=Depends(get_current_user), engine=Depends(get_engine)):
    changes = data.model_dump(exclude_unset=True)

    with engine.begin() as db:
        old_lead = find_lead(db, user, lead_id, lock=True)
        update_row(db, "leads", lead_id, user["company_id"], changes)
        new_lead = find_lead(db, user, lead_id)
        save_audit_log(db, user, "UPDATE", "lead", lead_id, request,
                       old_values=old_lead, new_values=new_lead)

    return new_lead


@router.delete("/{lead_id}", status_code=204)
def delete_lead(lead_id: int, request: Request,
                user=Depends(allow_roles(ADMIN)), engine=Depends(get_engine)):
    with engine.begin() as db:
        old_lead = find_lead(db, user, lead_id, lock=True)
        # Soft delete: the row stays, but every query skips rows where deleted_at is set.
        db.execute(
            text("UPDATE leads SET deleted_at = UTC_TIMESTAMP() WHERE id = :id AND company_id = :company_id"),
            {"id": lead_id, "company_id": user["company_id"]},
        )
        save_audit_log(db, user, "DELETE", "lead", lead_id, request, old_values=old_lead)

    return Response(status_code=204)


# ---------- Assign ----------

@router.patch("/{lead_id}/assign", response_model=LeadResponse)
def assign_lead(lead_id: int, data: AssignRequest, request: Request,
                user=Depends(allow_roles(ADMIN, MANAGER)), engine=Depends(get_engine)):
    with engine.begin() as db:
        # 1. The lead must belong to the current company (otherwise 404).
        old_lead = find_lead(db, user, lead_id, lock=True)
        # 2. The new user must exist, be active and be in the same company (otherwise 422).
        check_user_can_be_assigned(db, user["company_id"], data.user_id)

        update_row(db, "leads", lead_id, user["company_id"], {"assigned_to": data.user_id})
        new_lead = find_lead(db, user, lead_id)
        save_audit_log(db, user, "ASSIGN", "lead", lead_id, request,
                       old_values={"assigned_to": old_lead["assigned_to"]},
                       new_values={"assigned_to": data.user_id})

    return new_lead


# ---------- Convert to customer ----------

@router.post("/{lead_id}/convert", status_code=201, response_model=CustomerResponse)
def convert_lead(lead_id: int, request: Request,
                 user=Depends(get_current_user), engine=Depends(get_engine)):
    """Turn a lead into a customer.

    Four things happen in ONE transaction: create the customer, mark the lead as converted,
    add an activity, and write the audit log. If any step fails, all of them are undone.

    How we stop two customers being created when two requests arrive at the same time:
    1. SELECT ... FOR UPDATE locks the lead row. The second request has to WAIT at this
       line until the first request's transaction is finished.
    2. When the second request continues, it sees converted_at is already filled in,
       so it returns 409 Conflict.
    3. Safety net: the customers table has a UNIQUE key on (company_id, lead_id).
       Even if the lock was somehow skipped, MySQL would refuse a second customer.
    """
    try:
        with engine.begin() as db:
            lead = find_lead(db, user, lead_id, lock=True)

            if lead["converted_at"] is not None:
                raise HTTPException(409, "This lead has already been converted to a customer.")

            # Keep the useful information from the lead.
            result = db.execute(
                text("""
                    INSERT INTO customers (company_id, lead_id, assigned_to, first_name, last_name,
                                           email, phone, company_name)
                    VALUES (:company_id, :lead_id, :assigned_to, :first_name, :last_name,
                            :email, :phone, :company_name)
                """),
                {
                    "company_id": user["company_id"],
                    "lead_id": lead_id,
                    "assigned_to": lead["assigned_to"] or user["id"],
                    "first_name": lead["first_name"],
                    "last_name": lead["last_name"],
                    "email": lead["email"],
                    "phone": lead["phone"],
                    "company_name": lead["company_name"],
                },
            )
            customer_id = result.lastrowid

            db.execute(
                text("""
                    UPDATE leads SET converted_at = UTC_TIMESTAMP(), status = 'WON'
                    WHERE id = :id AND company_id = :company_id
                """),
                {"id": lead_id, "company_id": user["company_id"]},
            )

            db.execute(
                text("""
                    INSERT INTO activities (company_id, user_id, lead_id, customer_id, type, title, completed_at)
                    VALUES (:company_id, :user_id, :lead_id, :customer_id, 'NOTE',
                            'Lead converted to customer', UTC_TIMESTAMP())
                """),
                {"company_id": user["company_id"], "user_id": user["id"],
                 "lead_id": lead_id, "customer_id": customer_id},
            )

            save_audit_log(db, user, "CONVERT", "lead", lead_id, request,
                           old_values={"status": lead["status"]},
                           new_values={"status": "WON", "customer_id": customer_id})

            customer = db.execute(
                text("SELECT * FROM customers WHERE id = :id"), {"id": customer_id}
            ).mappings().one()

    except IntegrityError:
        # The UNIQUE key (company_id, lead_id) stopped a second customer (the safety net).
        raise HTTPException(409, "This lead has already been converted to a customer.")

    return customer


# ---------- Notes ----------

@router.post("/{lead_id}/notes", status_code=201, response_model=NoteResponse)
def add_note(lead_id: int, data: NoteCreate, request: Request,
             user=Depends(get_current_user), engine=Depends(get_engine)):
    with engine.begin() as db:
        # If the user cannot see the lead, they cannot add a note to it.
        find_lead(db, user, lead_id)

        result = db.execute(
            text("""
                INSERT INTO notes (company_id, lead_id, user_id, content)
                VALUES (:company_id, :lead_id, :user_id, :content)
            """),
            {"company_id": user["company_id"], "lead_id": lead_id,
             "user_id": user["id"], "content": data.content},
        )
        note = db.execute(
            text("SELECT * FROM notes WHERE id = :id"), {"id": result.lastrowid}
        ).mappings().one()
        save_audit_log(db, user, "CREATE", "note", note["id"], request, new_values=note)

    return note


@router.get("/{lead_id}/notes", response_model=NoteList)
def list_notes(lead_id: int,
               page: int = Query(1, ge=1),
               per_page: int = Query(25, ge=1, le=100),
               user=Depends(get_current_user), engine=Depends(get_engine)):
    with engine.connect() as db:
        find_lead(db, user, lead_id)

        params = {"company_id": user["company_id"], "lead_id": lead_id}
        where_sql = "company_id = :company_id AND lead_id = :lead_id"
        return paginate(
            db,
            select_sql=f"SELECT * FROM notes WHERE {where_sql} ORDER BY created_at DESC, id DESC",
            count_sql=f"SELECT COUNT(*) FROM notes WHERE {where_sql}",
            params=params,
            page=page,
            per_page=per_page,
        )
