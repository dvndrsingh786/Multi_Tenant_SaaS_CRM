from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ShortText, StrictModel


class RegisterRequest(StrictModel):
    company_name: ShortText
    name: ShortText
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, password):
        has_letter = any(character.isalpha() for character in password)
        has_number = any(character.isdigit() for character in password)
        if not (has_letter and has_number):
            raise ValueError("Password must contain at least one letter and one number.")
        return password


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
