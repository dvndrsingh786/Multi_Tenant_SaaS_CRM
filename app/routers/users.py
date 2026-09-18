"""User management inside one company.

Rules:
- ADMIN can create, update and delete users.
- MANAGER can see the list of users (needed to assign leads), but cannot change them.
- SALES_AGENT can only see their own user record.
- Nobody can create an ADMIN, promote someone to ADMIN, or move a user to another company.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import text

from app.audit import save_audit_log
from app.database import get_engine
from app.plan_limits import check_user_limit
from app.schemas.auth import UserResponse
from app.schemas.users import UserCreate, UserList, UserUpdate
from app.security import ADMIN, MANAGER, SALES_AGENT, allow_roles, get_current_user, hash_password
from app.utils import like_pattern, paginate, update_row

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

USER_COLUMNS = "id, company_id, name, email, role, status, created_at, updated_at"


def find_user(db, company_id, user_id):
    """Find a user INSIDE this company. A user from another company is treated as "not found"."""
    user = db.execute(
        text(f"""
            SELECT {USER_COLUMNS} FROM users
            WHERE id = :id AND company_id = :company_id AND deleted_at IS NULL
        """),
        {"id": user_id, "company_id": company_id},
    ).mappings().first()

    if user is None:
        # We say 404, not 403, so nobody can find out that the id exists in another company.
        raise HTTPException(404, "User not found.")
    return user


def log_out_everywhere(db, user_id):
    db.execute(text("DELETE FROM auth_tokens WHERE user_id = :user_id"), {"user_id": user_id})


@router.get("", response_model=UserList)
def list_users(
    page: int = Query(1, ge=1, le=10000),
    per_page: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    role: Literal["ADMIN", "MANAGER", "SALES_AGENT"] | None = None,
    status: Literal["ACTIVE", "INACTIVE"] | None = None,
    user=Depends(allow_roles(ADMIN, MANAGER)),
    engine=Depends(get_engine),
):
    # Start with the rules that always apply, then add the optional filters.
    conditions = ["company_id = :company_id", "deleted_at IS NULL"]
    params = {"company_id": user["company_id"]}

    if search:
        conditions.append("(name LIKE :search OR email LIKE :search)")
        params["search"] = like_pattern(search)
    if role:
        conditions.append("role = :role")
        params["role"] = role
    if status:
        conditions.append("status = :status")
        params["status"] = status

    where_sql = " AND ".join(conditions)
    with engine.connect() as db:
        return paginate(
            db,
            select_sql=f"SELECT {USER_COLUMNS} FROM users WHERE {where_sql} ORDER BY id",
            count_sql=f"SELECT COUNT(*) FROM users WHERE {where_sql}",
            params=params,
            page=page,
            per_page=per_page,
        )


@router.post("", status_code=201, response_model=UserResponse)
def create_user(data: UserCreate, request: Request,
                user=Depends(allow_roles(ADMIN)), engine=Depends(get_engine)):
    email = data.email.lower()
    password_hash = hash_password(data.password)

    with engine.begin() as db:
        check_user_limit(db, user["company_id"])

        existing = db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).first()
        if existing:
            raise HTTPException(409, "A user with this email already exists.")

        # company_id comes from the logged-in admin, never from the request body.
        result = db.execute(
            text("""
                INSERT INTO users (company_id, name, email, password_hash, role)
                VALUES (:company_id, :name, :email, :password_hash, :role)
            """),
            {"company_id": user["company_id"], "name": data.name, "email": email,
             "password_hash": password_hash, "role": data.role},
        )
        new_user = find_user(db, user["company_id"], result.lastrowid)
        save_audit_log(db, user, "CREATE", "user", new_user["id"], request, new_values=new_user)

    return new_user


@router.get("/{user_id}", response_model=UserResponse)
def show_user(user_id: int, user=Depends(get_current_user), engine=Depends(get_engine)):
    # A sales agent may only look at their own record.
    if user["role"] == SALES_AGENT and user_id != user["id"]:
        raise HTTPException(403, "You do not have permission to do this.")

    with engine.connect() as db:
        return find_user(db, user["company_id"], user_id)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, data: UserUpdate, request: Request,
                user=Depends(allow_roles(ADMIN)), engine=Depends(get_engine)):
    changes = data.model_dump(exclude_unset=True)

    with engine.begin() as db:
        old_user = find_user(db, user["company_id"], user_id)

        # The ADMIN account cannot be demoted or deactivated.
        # This also stops an admin from locking themselves out by accident.
        if old_user["role"] == ADMIN and ("role" in changes or "status" in changes):
            raise HTTPException(403, "The role and status of an ADMIN cannot be changed.")

        update_row(db, "users", user_id, user["company_id"], changes)

        # A deactivated user is logged out straight away.
        if changes.get("status") == "INACTIVE":
            log_out_everywhere(db, user_id)

        new_user = find_user(db, user["company_id"], user_id)
        save_audit_log(db, user, "UPDATE", "user", user_id, request,
                       old_values=old_user, new_values=new_user)

    return new_user


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, request: Request,
                user=Depends(allow_roles(ADMIN)), engine=Depends(get_engine)):
    with engine.begin() as db:
        old_user = find_user(db, user["company_id"], user_id)
        if old_user["role"] == ADMIN:
            raise HTTPException(403, "An ADMIN account cannot be deleted.")

        # Soft delete: keep the row (old records still point to it), but mark it as deleted.
        db.execute(
            text("""
                UPDATE users SET deleted_at = UTC_TIMESTAMP(), status = 'INACTIVE'
                WHERE id = :id AND company_id = :company_id
            """),
            {"id": user_id, "company_id": user["company_id"]},
        )
        log_out_everywhere(db, user_id)
        save_audit_log(db, user, "DELETE", "user", user_id, request, old_values=old_user)

    return Response(status_code=204)
