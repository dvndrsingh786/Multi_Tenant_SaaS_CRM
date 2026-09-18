"""Contacts.

Who can see which contacts:
- ADMIN and MANAGER: every contact in their company.
- SALES_AGENT: only the contacts they own (owner_id).

Everyone can create, update and delete the contacts they can see.
A sales agent's contacts are always owned by themselves.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import text

from app.audit import save_audit_log
from app.database import get_engine
from app.finders import find_contact
from app.schemas.contacts import ContactCreate, ContactList, ContactResponse, ContactUpdate
from app.security import SALES_AGENT, get_current_user
from app.utils import check_user_can_be_assigned, like_pattern, paginate, update_row

router = APIRouter(prefix="/api/v1/contacts", tags=["Contacts"])


@router.get("", response_model=ContactList)
def list_contacts(
    page: int = Query(1, ge=1, le=10000),
    per_page: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    owner_id: int | None = None,
    sort_by: Literal["created_at", "updated_at", "first_name", "last_name"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    user=Depends(get_current_user),
    engine=Depends(get_engine),
):
    conditions = ["company_id = :company_id", "deleted_at IS NULL"]
    params = {"company_id": user["company_id"]}

    if user["role"] == SALES_AGENT:
        conditions.append("owner_id = :current_user_id")
        params["current_user_id"] = user["id"]

    if search:
        conditions.append("""(first_name LIKE :search OR last_name LIKE :search
                              OR email LIKE :search OR company_name LIKE :search)""")
        params["search"] = like_pattern(search)
    if owner_id:
        conditions.append("owner_id = :owner_id")
        params["owner_id"] = owner_id

    where_sql = " AND ".join(conditions)
    order_sql = f"ORDER BY {sort_by} {sort_order}, id {sort_order}"

    with engine.connect() as db:
        return paginate(
            db,
            select_sql=f"SELECT * FROM contacts WHERE {where_sql} {order_sql}",
            count_sql=f"SELECT COUNT(*) FROM contacts WHERE {where_sql}",
            params=params,
            page=page,
            per_page=per_page,
        )


@router.post("", status_code=201, response_model=ContactResponse)
def create_contact(data: ContactCreate, request: Request,
                   user=Depends(get_current_user), engine=Depends(get_engine)):
    contact = data.model_dump()

    if user["role"] == SALES_AGENT:
        if contact["owner_id"] not in (None, user["id"]):
            raise HTTPException(403, "Sales agents can only create contacts for themselves.")
        contact["owner_id"] = user["id"]
    elif contact["owner_id"] is None:
        contact["owner_id"] = user["id"]

    contact["company_id"] = user["company_id"]

    with engine.begin() as db:
        check_user_can_be_assigned(db, user["company_id"], contact["owner_id"])

        result = db.execute(
            text("""
                INSERT INTO contacts (company_id, owner_id, first_name, last_name, email,
                                      phone, job_title, company_name)
                VALUES (:company_id, :owner_id, :first_name, :last_name, :email,
                        :phone, :job_title, :company_name)
            """),
            contact,
        )
        new_contact = find_contact(db, user, result.lastrowid)
        save_audit_log(db, user, "CREATE", "contact", new_contact["id"], request, new_values=new_contact)

    return new_contact


@router.get("/{contact_id}", response_model=ContactResponse)
def show_contact(contact_id: int, user=Depends(get_current_user), engine=Depends(get_engine)):
    with engine.connect() as db:
        return find_contact(db, user, contact_id)


@router.patch("/{contact_id}", response_model=ContactResponse)
def update_contact(contact_id: int, data: ContactUpdate, request: Request,
                   user=Depends(get_current_user), engine=Depends(get_engine)):
    changes = data.model_dump(exclude_unset=True)

    if "owner_id" in changes:
        if user["role"] == SALES_AGENT:
            raise HTTPException(403, "Sales agents cannot change the owner of a contact.")
        if changes["owner_id"] is None:
            raise HTTPException(422, "owner_id cannot be empty.")

    with engine.begin() as db:
        old_contact = find_contact(db, user, contact_id, lock=True)
        if "owner_id" in changes:
            check_user_can_be_assigned(db, user["company_id"], changes["owner_id"])

        update_row(db, "contacts", contact_id, user["company_id"], changes)
        new_contact = find_contact(db, user, contact_id)
        save_audit_log(db, user, "UPDATE", "contact", contact_id, request,
                       old_values=old_contact, new_values=new_contact)

    return new_contact


@router.delete("/{contact_id}", status_code=204)
def delete_contact(contact_id: int, request: Request,
                   user=Depends(get_current_user), engine=Depends(get_engine)):
    with engine.begin() as db:
        old_contact = find_contact(db, user, contact_id, lock=True)
        db.execute(
            text("UPDATE contacts SET deleted_at = UTC_TIMESTAMP() WHERE id = :id AND company_id = :company_id"),
            {"id": contact_id, "company_id": user["company_id"]},
        )
        save_audit_log(db, user, "DELETE", "contact", contact_id, request, old_values=old_contact)

    return Response(status_code=204)
