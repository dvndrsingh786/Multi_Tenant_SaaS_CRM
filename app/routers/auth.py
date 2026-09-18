from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import text

from app.audit import save_audit_log
from app.database import get_engine
from app.rate_limit import check_rate_limit
from app.schemas.auth import (
    LoginRequest, RegisterRequest, RegisterResponse, TokenResponse, UserResponse,
)
from app.security import (
    TOKEN_LIFETIME_HOURS, create_token, get_current_user, hash_password, hash_token,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

# The columns we send back for a user. Never includes password_hash.
USER_COLUMNS = "id, company_id, name, email, role, status, created_at, updated_at"

# Used when the email does not exist, so a wrong email takes as long as a wrong password.
# Otherwise an attacker could measure the time and learn which emails have accounts.
FAKE_PASSWORD_HASH = hash_password("this-is-not-a-real-password-1")


def get_ip_address(request):
    return request.client.host if request.client else "unknown"


@router.post("/register", status_code=201, response_model=RegisterResponse)
def register(data: RegisterRequest, request: Request, engine=Depends(get_engine)):
    """Create a new company and its first user. That user becomes the ADMIN."""
    check_rate_limit(engine, f"register:{get_ip_address(request)}", max_requests=10)

    email = data.email.lower()
    # Hashing is slow on purpose, so do it before we open the transaction.
    password_hash = hash_password(data.password)

    # engine.begin() starts a transaction. Everything inside is saved together at the end,
    # or everything is undone if there is an error. We never get a company without an admin.
    with engine.begin() as db:
        existing = db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).first()
        if existing:
            raise HTTPException(409, "An account with this email already exists.")

        result = db.execute(
            text("INSERT INTO companies (name) VALUES (:name)"),
            {"name": data.company_name},
        )
        company_id = result.lastrowid

        # The role is always ADMIN here. The client cannot choose it.
        result = db.execute(
            text("""
                INSERT INTO users (company_id, name, email, password_hash, role)
                VALUES (:company_id, :name, :email, :password_hash, 'ADMIN')
            """),
            {"company_id": company_id, "name": data.name, "email": email, "password_hash": password_hash},
        )
        user_id = result.lastrowid

        # Every new company starts on the FREE plan.
        db.execute(
            text("""
                INSERT INTO subscriptions (company_id, plan_id)
                SELECT :company_id, id FROM plans WHERE name = 'FREE'
            """),
            {"company_id": company_id},
        )

        user = db.execute(
            text(f"SELECT {USER_COLUMNS} FROM users WHERE id = :id"), {"id": user_id}
        ).mappings().one()

        save_audit_log(db, user, "CREATE", "company", company_id, request,
                       new_values={"name": data.company_name})
        save_audit_log(db, user, "CREATE", "user", user_id, request, new_values=user)

    return {"company_id": company_id, "company_name": data.company_name, "user": user}


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, engine=Depends(get_engine)):
    email = data.email.lower()
    # Max 5 tries per minute for the same email from the same IP address (stops password guessing).
    check_rate_limit(engine, f"login:{get_ip_address(request)}:{email}", max_requests=5)

    with engine.begin() as db:
        user = db.execute(
            text("""
                SELECT users.id, users.company_id, users.password_hash
                FROM users
                JOIN companies ON companies.id = users.company_id
                WHERE users.email = :email
                  AND users.status = 'ACTIVE'
                  AND users.deleted_at IS NULL
                  AND companies.status = 'ACTIVE'
            """),
            {"email": email},
        ).mappings().first()

        if user is None:
            verify_password(data.password, FAKE_PASSWORD_HASH)
            raise HTTPException(401, "Invalid email or password.")

        if not verify_password(data.password, user["password_hash"]):
            raise HTTPException(401, "Invalid email or password.")

        # The client gets the real token. The database only keeps its hash.
        token = create_token()
        db.execute(
            text("""
                INSERT INTO auth_tokens (user_id, token_hash, expires_at)
                VALUES (:user_id, :token_hash, DATE_ADD(UTC_TIMESTAMP(), INTERVAL :hours HOUR))
            """),
            {"user_id": user["id"], "token_hash": hash_token(token), "hours": TOKEN_LIFETIME_HOURS},
        )
        save_audit_log(db, user, "LOGIN", "user", user["id"], request)

    return {"access_token": token, "expires_in_seconds": TOKEN_LIFETIME_HOURS * 3600}


@router.post("/logout", status_code=204)
def logout(request: Request, user=Depends(get_current_user), engine=Depends(get_engine)):
    # Deleting the token means it can never be used again.
    with engine.begin() as db:
        db.execute(text("DELETE FROM auth_tokens WHERE id = :id"), {"id": user["token_id"]})
        save_audit_log(db, user, "LOGOUT", "user", user["id"], request)
    return Response(status_code=204)


@router.get("/me", response_model=UserResponse)
def me(user=Depends(get_current_user), engine=Depends(get_engine)):
    with engine.connect() as db:
        return db.execute(
            text(f"SELECT {USER_COLUMNS} FROM users WHERE id = :id"), {"id": user["id"]}
        ).mappings().one()
