from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.schemas.common import Phone, ShortText, StrictModel


class CompanyResponse(BaseModel):
    id: int
    name: str
    email: str | None
    phone: str | None
    website: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class CompanyUpdate(StrictModel):
    # "name: ShortText = None" means: the field is optional, but if you send it, it cannot be null.
    # "email: EmailStr | None = None" means: optional, and you may send null to clear it.
    # status is not here on purpose: a company cannot suspend or un-suspend itself.
    name: ShortText = None
    email: EmailStr | None = None
    phone: Phone | None = None
    website: ShortText | None = None
