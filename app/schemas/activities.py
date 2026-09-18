from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.common import LongText, PageInfo, ShortText, StrictModel, UtcDateTime

ActivityType = Literal["CALL", "EMAIL", "MEETING", "TASK", "NOTE"]


class ActivityCreate(StrictModel):
    # user_id is not here: an activity always belongs to the user who creates it.
    type: ActivityType
    title: ShortText
    description: LongText | None = None
    due_at: UtcDateTime | None = None
    completed_at: UtcDateTime | None = None
    lead_id: int | None = None
    customer_id: int | None = None
    deal_id: int | None = None


class ActivityUpdate(StrictModel):
    type: ActivityType = None
    title: ShortText = None
    description: LongText | None = None
    due_at: UtcDateTime | None = None
    completed_at: UtcDateTime | None = None
    lead_id: int | None = None
    customer_id: int | None = None
    deal_id: int | None = None


class ActivityResponse(BaseModel):
    id: int
    company_id: int
    user_id: int
    lead_id: int | None
    customer_id: int | None
    deal_id: int | None
    type: str
    title: str
    description: str | None
    due_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ActivityList(BaseModel):
    data: list[ActivityResponse]
    meta: PageInfo
