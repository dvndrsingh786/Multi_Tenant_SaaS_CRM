"""The logged-in user's own notifications (created by the reminder job)."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from app.database import get_engine
from app.schemas.common import PageInfo
from app.security import get_current_user
from app.utils import paginate

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


class NotificationResponse(BaseModel):
    id: int
    activity_id: int
    message: str
    is_read: bool
    created_at: datetime


class NotificationList(BaseModel):
    data: list[NotificationResponse]
    meta: PageInfo


@router.get("", response_model=NotificationList)
def list_my_notifications(page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=100),
                          user=Depends(get_current_user), engine=Depends(get_engine)):
    # Always only the current user's notifications, even for admins.
    where_sql = "company_id = :company_id AND user_id = :user_id"
    params = {"company_id": user["company_id"], "user_id": user["id"]}
    with engine.connect() as db:
        return paginate(
            db,
            select_sql=f"SELECT * FROM notifications WHERE {where_sql} ORDER BY id DESC",
            count_sql=f"SELECT COUNT(*) FROM notifications WHERE {where_sql}",
            params=params,
            page=page,
            per_page=per_page,
        )


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_as_read(notification_id: int, user=Depends(get_current_user), engine=Depends(get_engine)):
    params = {"id": notification_id, "company_id": user["company_id"], "user_id": user["id"]}
    where_sql = "id = :id AND company_id = :company_id AND user_id = :user_id"

    with engine.begin() as db:
        db.execute(text(f"UPDATE notifications SET is_read = TRUE WHERE {where_sql}"), params)
        notification = db.execute(text(f"SELECT * FROM notifications WHERE {where_sql}"), params).mappings().first()

    if notification is None:
        raise HTTPException(404, "Notification not found.")
    return notification
