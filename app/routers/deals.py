"""Deals (the sales pipeline).

Who can see which deals:
- ADMIN and MANAGER: every deal in their company.
- SALES_AGENT: only the deals assigned to them ("manage their deals").

Everyone can create, update, move and delete the deals they can see.
Only ADMIN and MANAGER can give a deal to another user.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import text

from app.audit import save_audit_log
from app.database import get_engine
from app.finders import check_linked_records, find_deal
from app.schemas.deals import DealCreate, DealList, DealResponse, DealStage, DealStageUpdate, DealUpdate
from app.security import SALES_AGENT, get_current_user
from app.utils import check_user_can_be_assigned, like_pattern, paginate, update_row

router = APIRouter(prefix="/api/v1/deals", tags=["Deals"])


@router.get("", response_model=DealList)
def list_deals(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    stage: DealStage | None = None,
    assigned_to: int | None = None,
    customer_id: int | None = None,
    sort_by: Literal["created_at", "updated_at", "value", "expected_close_date", "title"] = "created_at",
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
        conditions.append("title LIKE :search")
        params["search"] = like_pattern(search)
    if stage:
        conditions.append("stage = :stage")
        params["stage"] = stage
    if assigned_to:
        conditions.append("assigned_to = :assigned_to")
        params["assigned_to"] = assigned_to
    if customer_id:
        conditions.append("customer_id = :customer_id")
        params["customer_id"] = customer_id

    where_sql = " AND ".join(conditions)
    order_sql = f"ORDER BY {sort_by} {sort_order}, id {sort_order}"

    with engine.connect() as db:
        return paginate(
            db,
            select_sql=f"SELECT * FROM deals WHERE {where_sql} {order_sql}",
            count_sql=f"SELECT COUNT(*) FROM deals WHERE {where_sql}",
            params=params,
            page=page,
            per_page=per_page,
        )


@router.post("", status_code=201, response_model=DealResponse)
def create_deal(data: DealCreate, request: Request,
                user=Depends(get_current_user), engine=Depends(get_engine)):
    deal = data.model_dump()

    if user["role"] == SALES_AGENT:
        if deal["assigned_to"] not in (None, user["id"]):
            raise HTTPException(403, "Sales agents can only create deals for themselves.")
        deal["assigned_to"] = user["id"]

    deal["company_id"] = user["company_id"]

    with engine.begin() as db:
        # The customer and lead must be in the same company (and visible to this user).
        check_linked_records(db, user, lead_id=deal["lead_id"], customer_id=deal["customer_id"])
        if deal["assigned_to"] is not None:
            check_user_can_be_assigned(db, user["company_id"], deal["assigned_to"])

        result = db.execute(
            text("""
                INSERT INTO deals (company_id, customer_id, lead_id, assigned_to, title, description,
                                   value, stage, expected_close_date)
                VALUES (:company_id, :customer_id, :lead_id, :assigned_to, :title, :description,
                        :value, :stage, :expected_close_date)
            """),
            deal,
        )
        new_deal = find_deal(db, user, result.lastrowid)
        save_audit_log(db, user, "CREATE", "deal", new_deal["id"], request, new_values=new_deal)

    return new_deal


@router.get("/{deal_id}", response_model=DealResponse)
def show_deal(deal_id: int, user=Depends(get_current_user), engine=Depends(get_engine)):
    with engine.connect() as db:
        return find_deal(db, user, deal_id)


@router.patch("/{deal_id}", response_model=DealResponse)
def update_deal(deal_id: int, data: DealUpdate, request: Request,
                user=Depends(get_current_user), engine=Depends(get_engine)):
    changes = data.model_dump(exclude_unset=True)

    if "assigned_to" in changes and user["role"] == SALES_AGENT:
        raise HTTPException(403, "Sales agents cannot give a deal to another user.")

    with engine.begin() as db:
        old_deal = find_deal(db, user, deal_id, lock=True)
        check_linked_records(db, user, lead_id=changes.get("lead_id"), customer_id=changes.get("customer_id"))
        if changes.get("assigned_to") is not None:
            check_user_can_be_assigned(db, user["company_id"], changes["assigned_to"])

        update_row(db, "deals", deal_id, user["company_id"], changes)
        new_deal = find_deal(db, user, deal_id)
        save_audit_log(db, user, "UPDATE", "deal", deal_id, request,
                       old_values=old_deal, new_values=new_deal)

    return new_deal


@router.patch("/{deal_id}/stage", response_model=DealResponse)
def change_deal_stage(deal_id: int, data: DealStageUpdate, request: Request,
                      user=Depends(get_current_user), engine=Depends(get_engine)):
    """Move a deal through the pipeline: NEW -> QUALIFIED -> PROPOSAL -> NEGOTIATION -> WON / LOST."""
    with engine.begin() as db:
        old_deal = find_deal(db, user, deal_id, lock=True)
        update_row(db, "deals", deal_id, user["company_id"], {"stage": data.stage})
        new_deal = find_deal(db, user, deal_id)
        save_audit_log(db, user, "UPDATE", "deal", deal_id, request,
                       old_values={"stage": old_deal["stage"]}, new_values={"stage": data.stage})

    return new_deal


@router.delete("/{deal_id}", status_code=204)
def delete_deal(deal_id: int, request: Request,
                user=Depends(get_current_user), engine=Depends(get_engine)):
    with engine.begin() as db:
        old_deal = find_deal(db, user, deal_id, lock=True)
        db.execute(
            text("UPDATE deals SET deleted_at = UTC_TIMESTAMP() WHERE id = :id AND company_id = :company_id"),
            {"id": deal_id, "company_id": user["company_id"]},
        )
        save_audit_log(db, user, "DELETE", "deal", deal_id, request, old_values=old_deal)

    return Response(status_code=204)
