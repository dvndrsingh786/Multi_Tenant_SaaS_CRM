from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr

from app.schemas.common import LongText, Money, Name, PageInfo, Phone, ShortText, StrictModel

LeadStatus = Literal["NEW", "CONTACTED", "QUALIFIED", "PROPOSAL", "NEGOTIATION", "WON", "LOST"]
LeadSource = Literal["WEBSITE", "REFERRAL", "LINKEDIN", "EMAIL", "PHONE", "ADVERTISEMENT", "OTHER"]


class LeadCreate(StrictModel):
    first_name: Name
    last_name: Name
    email: EmailStr | None = None
    phone: Phone | None = None
    company_name: ShortText | None = None
    job_title: ShortText | None = None
    source: LeadSource = "OTHER"
    status: LeadStatus = "NEW"
    estimated_value: Money = Decimal("0")
    assigned_to: int | None = None


class LeadUpdate(StrictModel):
    # All optional: only the fields that are sent get changed.
    # assigned_to is not here: use PATCH /leads/{id}/assign instead.
    first_name: Name = None
    last_name: Name = None
    email: EmailStr | None = None
    phone: Phone | None = None
    company_name: ShortText | None = None
    job_title: ShortText | None = None
    source: LeadSource = None
    status: LeadStatus = None
    estimated_value: Money = None


class LeadResponse(BaseModel):
    id: int
    company_id: int
    assigned_to: int | None
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    company_name: str | None
    job_title: str | None
    source: str
    status: str
    estimated_value: float
    converted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LeadList(BaseModel):
    data: list[LeadResponse]
    meta: PageInfo


class AssignRequest(StrictModel):
    user_id: int


class NoteCreate(StrictModel):
    content: LongText


class NoteResponse(BaseModel):
    id: int
    lead_id: int
    user_id: int
    content: str
    created_at: datetime


class NoteList(BaseModel):
    data: list[NoteResponse]
    meta: PageInfo
