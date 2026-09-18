"""Pieces shared by all the request and response models."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints


class StrictModel(BaseModel):
    # extra="forbid" rejects any field we did not list (for example "company_id" or "role").
    # This is how we stop "mass assignment": the client can only send the fields we allow.
    model_config = ConfigDict(extra="forbid")


# Reusable field types. strip_whitespace removes spaces at the start and end.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]
Money = Annotated[Decimal, Field(ge=0, max_digits=15, decimal_places=2)]


def check_password_strength(password):
    has_letter = any(character.isalpha() for character in password)
    has_number = any(character.isdigit() for character in password)
    if not (has_letter and has_number):
        raise ValueError("Password must contain at least one letter and one number.")
    return password


# 8 to 128 characters, with at least one letter and one number.
Password = Annotated[str, Field(min_length=8, max_length=128), AfterValidator(check_password_strength)]


def convert_to_utc(value):
    # "2026-09-20T10:00:00+02:00" becomes 08:00 UTC. The database stores everything in UTC.
    # A time without a time zone is treated as UTC already.
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


UtcDateTime = Annotated[datetime, AfterValidator(convert_to_utc)]


class PageInfo(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int
