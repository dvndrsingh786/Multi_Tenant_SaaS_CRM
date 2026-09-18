"""The logged-in user's own company.

There is no company id in these URLs. The company always comes from the login token,
so a user can only ever see or change their own company.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import text

from app.audit import save_audit_log
from app.database import get_engine
from app.schemas.company import CompanyResponse, CompanyUpdate
from app.security import ADMIN, allow_roles, get_current_user

router = APIRouter(prefix="/api/v1/company", tags=["Company"])

COMPANY_COLUMNS = "id, name, email, phone, website, status, created_at, updated_at"


def get_company(db, company_id):
    return db.execute(
        text(f"SELECT {COMPANY_COLUMNS} FROM companies WHERE id = :id"), {"id": company_id}
    ).mappings().one()


@router.get("", response_model=CompanyResponse)
def show_company(user=Depends(get_current_user), engine=Depends(get_engine)):
    with engine.connect() as db:
        return get_company(db, user["company_id"])


@router.patch("", response_model=CompanyResponse)
def update_company(data: CompanyUpdate, request: Request,
                   user=Depends(allow_roles(ADMIN)), engine=Depends(get_engine)):
    # exclude_unset=True: only the fields the client actually sent.
    changes = data.model_dump(exclude_unset=True)

    with engine.begin() as db:
        old_company = get_company(db, user["company_id"])

        if changes:
            # Builds for example: UPDATE companies SET name = :name, phone = :phone WHERE id = :id
            set_sql = ", ".join(f"{column} = :{column}" for column in changes)
            params = dict(changes)
            params["id"] = user["company_id"]
            db.execute(text(f"UPDATE companies SET {set_sql} WHERE id = :id"), params)

        new_company = get_company(db, user["company_id"])
        save_audit_log(db, user, "UPDATE", "company", user["company_id"], request,
                       old_values=old_company, new_values=new_company)

    return new_company
