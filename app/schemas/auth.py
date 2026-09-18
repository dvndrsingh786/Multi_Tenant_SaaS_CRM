from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import Password, ShortText, StrictModel


class RegisterRequest(StrictModel):
    company_name: ShortText
    name: ShortText
    email: EmailStr
    password: Password


class LoginRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class UserResponse(BaseModel):
    id: int
    company_id: int
    name: str
    email: str
    role: str
    status: str
    created_at: datetime
    updated_at: datetime


class RegisterResponse(BaseModel):
    company_id: int
    company_name: str
    user: UserResponse
