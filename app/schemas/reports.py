from datetime import datetime
from typing import Any

from pydantic import BaseModel, Json

from app.schemas.common import PageInfo


class DashboardResponse(BaseModel):
    total_leads: int
    new_leads: int
    qualified_leads: int
    won_leads: int
    lost_leads: int
    leads_by_status: dict[str, int]
    total_customers: int
    total_deals: int
    pipeline_value: float  # value of open deals (not WON and not LOST)
    won_value: float       # value of WON deals


class SearchResult(BaseModel):
    type: str      # "lead", "contact", "customer" or "deal"
    id: int
    title: str
    subtitle: str | None
    created_at: datetime


class SearchResponse(BaseModel):
    data: list[SearchResult]
    meta: PageInfo


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    # MySQL gives JSON columns back as text. Json[...] turns that text into a real object.
    old_values: Json[dict[str, Any]] | None
    new_values: Json[dict[str, Any]] | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


class AuditLogList(BaseModel):
    data: list[AuditLogResponse]
    meta: PageInfo
