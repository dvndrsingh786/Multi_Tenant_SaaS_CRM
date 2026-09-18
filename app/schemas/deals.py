from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.schemas.common import LongText, Money, PageInfo, ShortText, StrictModel

DealStage = Literal["NEW", "QUALIFIED", "PROPOSAL", "NEGOTIATION", "WON", "LOST"]


class DealCreate(StrictModel):
    title: ShortText
    description: LongText | None = None
    value: Money = Decimal("0")
    stage: DealStage = "NEW"
    expected_close_date: date | None = None
    customer_id: int | None = None
    lead_id: int | None = None
    assigned_to: int | None = None


class DealUpdate(StrictModel):
    # stage is not here: use PATCH /deals/{id}/stage.
    title: ShortText = None
    description: LongText | None = None
    value: Money = None
    expected_close_date: date | None = None
    customer_id: int | None = None
    lead_id: int | None = None
    assigned_to: int | None = None


class DealStageUpdate(StrictModel):
    stage: DealStage


class DealResponse(BaseModel):
    id: int
    company_id: int
    customer_id: int | None
    lead_id: int | None
    assigned_to: int | None
    title: str
    description: str | None
    value: float
    stage: str
    expected_close_date: date | None
    created_at: datetime
    updated_at: datetime


class DealList(BaseModel):
    data: list[DealResponse]
    meta: PageInfo
