"""Pieces shared by all the request and response models."""
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


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


class PageInfo(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int
