from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.schemas.common import Name, PageInfo, Phone, ShortText, StrictModel


class ContactCreate(StrictModel):
    first_name: Name
    last_name: Name
    email: EmailStr | None = None
    phone: Phone | None = None
    job_title: ShortText | None = None
    company_name: ShortText | None = None
    owner_id: int | None = None


class ContactUpdate(StrictModel):
    first_name: Name = None
    last_name: Name = None
    email: EmailStr | None = None
    phone: Phone | None = None
    job_title: ShortText | None = None
    company_name: ShortText | None = None
    owner_id: int | None = None


class ContactResponse(BaseModel):
    id: int
    company_id: int
    owner_id: int | None
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    job_title: str | None
    company_name: str | None
    created_at: datetime
    updated_at: datetime


class ContactList(BaseModel):
    data: list[ContactResponse]
    meta: PageInfo
