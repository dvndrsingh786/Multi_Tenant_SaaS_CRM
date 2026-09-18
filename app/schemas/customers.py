from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr

from app.schemas.common import Name, PageInfo, Phone, ShortText, StrictModel

CustomerStatus = Literal["ACTIVE", "INACTIVE"]


class CustomerCreate(StrictModel):
    # lead_id is not here: a customer only gets a lead_id through POST /leads/{id}/convert.
    first_name: Name
    last_name: Name
    email: EmailStr | None = None
    phone: Phone | None = None
    company_name: ShortText | None = None
    status: CustomerStatus = "ACTIVE"
    assigned_to: int | None = None


class CustomerUpdate(StrictModel):
    first_name: Name = None
    last_name: Name = None
    email: EmailStr | None = None
    phone: Phone | None = None
    company_name: ShortText | None = None
    status: CustomerStatus = None
    assigned_to: int | None = None


class CustomerResponse(BaseModel):
    id: int
    company_id: int
    lead_id: int | None
    assigned_to: int | None
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    company_name: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class CustomerList(BaseModel):
    data: list[CustomerResponse]
    meta: PageInfo
