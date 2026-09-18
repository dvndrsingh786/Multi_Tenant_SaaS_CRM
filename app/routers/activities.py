"""Activities: calls, emails, meetings, tasks and notes.

Who can see which activities:
- ADMIN and MANAGER: every activity in their company.
- SALES_AGENT: only their own activities.

An activity always belongs to the user who created it (user_id is never taken from the request).
The brief has no DELETE endpoint for activities, so there is none here.
"""
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text

from app.audit import save_audit_log
from app.database import get_engine
from app.finders import check_linked_records, find_activity
from app.schemas.activities import (
    ActivityCreate, ActivityList, ActivityResponse, ActivityType, ActivityUpdate,
)
from app.security import SALES_AGENT, get_current_user
from app.utils import paginate, update_row

router = APIRouter(prefix="/api/v1/activities", tags=["Activities"])


@router.get("", response_model=ActivityList)
def list_activities(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    type: ActivityType | None = None,
    lead_id: int | None = None,
    customer_id: int | None = None,
    deal_id: int | None = None,
    completed: bool | None = None,
    sort_by: Literal["created_at", "due_at"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    user=Depends(get_current_user),
    engine=Depends(get_engine),
):
    conditions = ["company_id = :company_id"]
    params = {"company_id": user["company_id"]}

    if user["role"] == SALES_AGENT:
        conditions.append("user_id = :current_user_id")
        params["current_user_id"] = user["id"]

    if type:
        conditions.append("type = :type")
        params["type"] = type
    if lead_id:
        conditions.append("lead_id = :lead_id")
        params["lead_id"] = lead_id
    if customer_id:
        conditions.append("customer_id = :customer_id")
        params["customer_id"] = customer_id
    if deal_id:
        conditions.append("deal_id = :deal_id")
        params["deal_id"] = deal_id
    if completed is True:
        conditions.append("completed_at IS NOT NULL")
    if completed is False:
        conditions.append("completed_at IS NULL")

    where_sql = " AND ".join(conditions)
    order_sql = f"ORDER BY {sort_by} {sort_order}, id {sort_order}"

    with engine.connect() as db:
        return paginate(
            db,
            select_sql=f"SELECT * FROM activities WHERE {where_sql} {order_sql}",
            count_sql=f"SELECT COUNT(*) FROM activities WHERE {where_sql}",
            params=params,
            page=page,
            per_page=per_page,
        )


@router.post("", status_code=201, response_model=ActivityResponse)
def create_activity(data: ActivityCreate, request: Request,
                    user=Depends(get_current_user), engine=Depends(get_engine)):
    activity = data.model_dump()
    activity["company_id"] = user["company_id"]
    activity["user_id"] = user["id"]

    with engine.begin() as db:
        check_linked_records(db, user, lead_id=activity["lead_id"],
                             customer_id=activity["customer_id"], deal_id=activity["deal_id"])

        result = db.execute(
            text("""
                INSERT INTO activities (company_id, user_id, lead_id, customer_id, deal_id,
                                        type, title, description, due_at, completed_at)
                VALUES (:company_id, :user_id, :lead_id, :customer_id, :deal_id,
                        :type, :title, :description, :due_at, :completed_at)
            """),
            activity,
        )
        new_activity = find_activity(db, user, result.lastrowid)
        save_audit_log(db, user, "CREATE", "activity", new_activity["id"], request, new_values=new_activity)

    return new_activity


@router.get("/{activity_id}", response_model=ActivityResponse)
def show_activity(activity_id: int, user=Depends(get_current_user), engine=Depends(get_engine)):
    with engine.connect() as db:
        return find_activity(db, user, activity_id)


@router.patch("/{activity_id}", response_model=ActivityResponse)
def update_activity(activity_id: int, data: ActivityUpdate, request: Request,
                    user=Depends(get_current_user), engine=Depends(get_engine)):
    changes = data.model_dump(exclude_unset=True)

    with engine.begin() as db:
        old_activity = find_activity(db, user, activity_id, lock=True)
        check_linked_records(db, user, lead_id=changes.get("lead_id"),
                             customer_id=changes.get("customer_id"), deal_id=changes.get("deal_id"))

        update_row(db, "activities", activity_id, user["company_id"], changes)
        new_activity = find_activity(db, user, activity_id)
        save_audit_log(db, user, "UPDATE", "activity", activity_id, request,
                       old_values=old_activity, new_values=new_activity)

    return new_activity
