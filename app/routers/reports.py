"""Dashboard, global search and audit logs.

All three follow the same visibility rules as the rest of the API:
- everything is filtered by the user's company,
- a SALES_AGENT only counts and finds their own records.
"""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from app.database import get_engine
from app.schemas.reports import AuditLogList, DashboardResponse, SearchResponse
from app.security import ADMIN, SALES_AGENT, allow_roles, get_current_user
from app.utils import like_pattern, paginate

router = APIRouter(prefix="/api/v1", tags=["Dashboard, Search & Audit Logs"])

LEAD_STATUSES = ["NEW", "CONTACTED", "QUALIFIED", "PROPOSAL", "NEGOTIATION", "WON", "LOST"]


def owner_filter(user, owner_column):
    """Extra SQL for sales agents: only rows they own. Empty for admins and managers."""
    if user["role"] == SALES_AGENT:
        return f" AND {owner_column} = :user_id"
    return ""


# ---------- Dashboard ----------

@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(user=Depends(get_current_user), engine=Depends(get_engine)):
    params = {"company_id": user["company_id"], "user_id": user["id"]}

    with engine.connect() as db:
        # One query counts the leads per status, for example {"NEW": 4, "WON": 2}.
        rows = db.execute(
            text(f"""
                SELECT status, COUNT(*) AS total FROM leads
                WHERE company_id = :company_id AND deleted_at IS NULL {owner_filter(user, "assigned_to")}
                GROUP BY status
            """),
            params,
        ).all()
        # Start every status at 0, so statuses without leads still show up.
        leads_by_status = {status: 0 for status in LEAD_STATUSES}
        for status, total in rows:
            leads_by_status[status] = total

        total_customers = db.execute(
            text(f"""
                SELECT COUNT(*) FROM customers
                WHERE company_id = :company_id AND deleted_at IS NULL {owner_filter(user, "assigned_to")}
            """),
            params,
        ).scalar()

        deals = db.execute(
            text(f"""
                SELECT COUNT(*) AS total_deals,
                       COALESCE(SUM(CASE WHEN stage NOT IN ('WON', 'LOST') THEN value END), 0) AS pipeline_value,
                       COALESCE(SUM(CASE WHEN stage = 'WON' THEN value END), 0) AS won_value
                FROM deals
                WHERE company_id = :company_id AND deleted_at IS NULL {owner_filter(user, "assigned_to")}
            """),
            params,
        ).mappings().one()

    return {
        "total_leads": sum(leads_by_status.values()),
        "new_leads": leads_by_status["NEW"],
        "qualified_leads": leads_by_status["QUALIFIED"],
        "won_leads": leads_by_status["WON"],
        "lost_leads": leads_by_status["LOST"],
        "leads_by_status": leads_by_status,
        "total_customers": total_customers,
        "total_deals": deals["total_deals"],
        "pipeline_value": deals["pipeline_value"],
        "won_value": deals["won_value"],
    }


# ---------- Global search ----------

@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(min_length=2, max_length=100),
    type: Literal["lead", "contact", "customer", "deal"] | None = None,
    page: int = Query(1, ge=1, le=10000),
    per_page: int = Query(25, ge=1, le=100),
    user=Depends(get_current_user),
    engine=Depends(get_engine),
):
    """Search leads, contacts, customers and deals at the same time.

    The search is case-insensitive because the tables use the utf8mb4_unicode_ci collation.
    Each part of the UNION has its own company filter (and owner filter for sales agents).
    """
    parts = {
        "lead": f"""
            SELECT 'lead' AS type, id, CONCAT(first_name, ' ', last_name) AS title,
                   email AS subtitle, created_at
            FROM leads
            WHERE company_id = :company_id AND deleted_at IS NULL {owner_filter(user, "assigned_to")}
              AND (first_name LIKE :q OR last_name LIKE :q OR email LIKE :q OR company_name LIKE :q)
        """,
        "contact": f"""
            SELECT 'contact' AS type, id, CONCAT(first_name, ' ', last_name) AS title,
                   email AS subtitle, created_at
            FROM contacts
            WHERE company_id = :company_id AND deleted_at IS NULL {owner_filter(user, "owner_id")}
              AND (first_name LIKE :q OR last_name LIKE :q OR email LIKE :q OR company_name LIKE :q)
        """,
        "customer": f"""
            SELECT 'customer' AS type, id, CONCAT(first_name, ' ', last_name) AS title,
                   email AS subtitle, created_at
            FROM customers
            WHERE company_id = :company_id AND deleted_at IS NULL {owner_filter(user, "assigned_to")}
              AND (first_name LIKE :q OR last_name LIKE :q OR email LIKE :q OR company_name LIKE :q)
        """,
        "deal": f"""
            SELECT 'deal' AS type, id, title, stage AS subtitle, created_at
            FROM deals
            WHERE company_id = :company_id AND deleted_at IS NULL {owner_filter(user, "assigned_to")}
              AND title LIKE :q
        """,
    }

    # Use only the chosen type, or all four joined together with UNION ALL.
    if type:
        union_sql = parts[type]
    else:
        union_sql = " UNION ALL ".join(parts.values())

    params = {"company_id": user["company_id"], "user_id": user["id"], "q": like_pattern(q)}

    with engine.connect() as db:
        return paginate(
            db,
            select_sql=f"SELECT * FROM ({union_sql}) AS results ORDER BY created_at DESC, type, id",
            count_sql=f"SELECT COUNT(*) FROM ({union_sql}) AS results",
            params=params,
            page=page,
            per_page=per_page,
        )


# ---------- Audit logs ----------

@router.get("/audit-logs", response_model=AuditLogList)
def list_audit_logs(
    action: Literal["CREATE", "UPDATE", "DELETE", "LOGIN", "LOGOUT", "ASSIGN", "CONVERT"] | None = None,
    entity_type: str | None = Query(None, max_length=50),
    entity_id: int | None = None,
    user_id: int | None = None,
    page: int = Query(1, ge=1, le=10000),
    per_page: int = Query(25, ge=1, le=100),
    user=Depends(allow_roles(ADMIN)),
    engine=Depends(get_engine),
):
    """Only ADMIN can read the audit log, and only for their own company."""
    conditions = ["company_id = :company_id"]
    params = {"company_id": user["company_id"]}

    if action:
        conditions.append("action = :action")
        params["action"] = action
    if entity_type:
        conditions.append("entity_type = :entity_type")
        params["entity_type"] = entity_type
    if entity_id:
        conditions.append("entity_id = :entity_id")
        params["entity_id"] = entity_id
    if user_id:
        conditions.append("user_id = :filter_user_id")
        params["filter_user_id"] = user_id

    where_sql = " AND ".join(conditions)
    with engine.connect() as db:
        return paginate(
            db,
            select_sql=f"SELECT * FROM audit_logs WHERE {where_sql} ORDER BY id DESC",
            count_sql=f"SELECT COUNT(*) FROM audit_logs WHERE {where_sql}",
            params=params,
            page=page,
            per_page=per_page,
        )
