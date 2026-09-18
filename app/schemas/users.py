from typing import Literal

from pydantic import BaseModel, EmailStr

from app.schemas.auth import UserResponse
from app.schemas.common import PageInfo, Password, ShortText, StrictModel

# ADMIN is not in this list on purpose. Nobody can create or promote a user to ADMIN
# through the API. The only ADMIN is the person who registered the company.
AssignableRole = Literal["MANAGER", "SALES_AGENT"]


class UserCreate(StrictModel):
    name: ShortText
    email: EmailStr
    password: Password
    role: AssignableRole


class UserUpdate(StrictModel):
    # company_id, email and password are not here, so they cannot be changed with this endpoint.
    name: ShortText = None
    role: AssignableRole = None
    status: Literal["ACTIVE", "INACTIVE"] = None


class UserList(BaseModel):
    data: list[UserResponse]
    meta: PageInfo
