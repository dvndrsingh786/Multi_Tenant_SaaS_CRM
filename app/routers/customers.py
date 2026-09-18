"""Customers.

Who can see which customers:
- ADMIN and MANAGER: every customer in their company.
- SALES_AGENT: only customers assigned to them.

Only ADMIN can create, update and delete customers (the brief says managers and
agents can "view" customers). Customers are also created by converting a lead.
"""
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import text

from app.audit import save_audit_log
from app.database import get_engine
from app.finders import find_customer
from app.schemas.customers import (
    CustomerCreate, CustomerList, CustomerResponse, CustomerStatus, CustomerUpdate,
)
from app.security import ADMIN, SALES_AGENT, allow_roles, get_current_user
from app.utils import check_user_can_be_assigned, like_pattern, paginate, update_row

router = APIRouter(prefix="/api/v1/customers", tags=["Customers"])


@router.get("", response_model=CustomerList)
def list_customers(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    status: CustomerStatus | None = None,
    assigned_to: int | None = None,
    sort_by: Literal["created_at", "updated_at", "first_name", "last_name"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    user=Depends(get_current_user),
    engine=Depends(get_engine),
):
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
    if assigned_to:
        conditions.append("assigned_to = :assigned_to")
        params["assigned_to"] = assigned_to

    where_sql = " AND ".join(conditions)
    order_sql = f"ORDER BY {sort_by} {sort_order}, id {sort_order}"

    with engine.connect() as db:
        return paginate(
            db,
            select_sql=f"SELECT * FROM customers WHERE {where_sql} {order_sql}",
            count_sql=f"SELECT COUNT(*) FROM customers WHERE {where_sql}",
            params=params,
            page=page,
            per_page=per_page,
        )


@router.post("", status_code=201, response_model=CustomerResponse)
def create_customer(data: CustomerCreate, request: Request,
                    user=Depends(allow_roles(ADMIN)), engine=Depends(get_engine)):
    customer = data.model_dump()
    customer["company_id"] = user["company_id"]

    with engine.begin() as db:
        if customer["assigned_to"] is not None:
            check_user_can_be_assigned(db, user["company_id"], customer["assigned_to"])

        result = db.execute(
            text("""
                INSERT INTO customers (company_id, assigned_to, first_name, last_name,
                                       email, phone, company_name, status)
                VALUES (:company_id, :assigned_to, :first_name, :last_name,
                        :email, :phone, :company_name, :status)
            """),
            customer,
        )
        new_customer = find_customer(db, user, result.lastrowid)
        save_audit_log(db, user, "CREATE", "customer", new_customer["id"], request, new_values=new_customer)

    return new_customer


@router.get("/{customer_id}", response_model=CustomerResponse)
def show_customer(customer_id: int, user=Depends(get_current_user), engine=Depends(get_engine)):
    with engine.connect() as db:
        return find_customer(db, user, customer_id)


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(customer_id: int, data: CustomerUpdate, request: Request,
                    user=Depends(allow_roles(ADMIN)), engine=Depends(get_engine)):
    changes = data.model_dump(exclude_unset=True)

    with engine.begin() as db:
        old_customer = find_customer(db, user, customer_id)
        if changes.get("assigned_to") is not None:
            check_user_can_be_assigned(db, user["company_id"], changes["assigned_to"])

        update_row(db, "customers", customer_id, user["company_id"], changes)
        new_customer = find_customer(db, user, customer_id)
        save_audit_log(db, user, "UPDATE", "customer", customer_id, request,
                       old_values=old_customer, new_values=new_customer)

    return new_customer


@router.delete("/{customer_id}", status_code=204)
def delete_customer(customer_id: int, request: Request,
                    user=Depends(allow_roles(ADMIN)), engine=Depends(get_engine)):
    with engine.begin() as db:
        old_customer = find_customer(db, user, customer_id)
        db.execute(
            text("UPDATE customers SET deleted_at = UTC_TIMESTAMP() WHERE id = :id AND company_id = :company_id"),
            {"id": customer_id, "company_id": user["company_id"]},
        )
        save_audit_log(db, user, "DELETE", "customer", customer_id, request, old_values=old_customer)

    return Response(status_code=204)
