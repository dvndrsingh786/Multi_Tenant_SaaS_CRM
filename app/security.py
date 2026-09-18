"""Passwords, login tokens, "who is logged in?" and role checks."""
import hashlib
import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import text

from app.database import get_engine

# The three roles a user can have.
ADMIN = "ADMIN"
MANAGER = "MANAGER"
SALES_AGENT = "SALES_AGENT"

TOKEN_LIFETIME_HOURS = 24

# ---------- Passwords ----------

# Argon2 is a slow, salted hashing algorithm made for passwords.
# We never store the real password, only this hash.
password_hasher = PasswordHash.recommended()


def hash_password(password):
    return password_hasher.hash(password)


def verify_password(password, password_hash):
    return password_hasher.verify(password, password_hash)


# ---------- Tokens ----------

def create_token():
    # 32 random bytes, impossible to guess.
    return secrets.token_urlsafe(32)


def hash_token(token):
    # We save only the SHA-256 hash of the token in the database.
    return hashlib.sha256(token.encode()).hexdigest()


# ---------- Who is logged in? ----------

# Reads the "Authorization: Bearer <token>" header.
# auto_error=False lets us send our own 401 message when the header is missing.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    engine=Depends(get_engine),
):
    """FastAPI runs this before every protected endpoint.

    It returns the logged-in user as a dict. Most importantly it gives us
    user["company_id"], which every query uses to stay inside the user's own company.
    """
    if credentials is None:
        raise HTTPException(401, "Not logged in. Send the header 'Authorization: Bearer <token>'.")

    with engine.connect() as db:
        user = db.execute(
            text("""
                SELECT users.id, users.company_id, users.name, users.email, users.role,
                       auth_tokens.id AS token_id
                FROM auth_tokens
                JOIN users ON users.id = auth_tokens.user_id
                JOIN companies ON companies.id = users.company_id
                WHERE auth_tokens.token_hash = :token_hash
                  AND auth_tokens.expires_at > UTC_TIMESTAMP()
                  AND users.status = 'ACTIVE'
                  AND users.deleted_at IS NULL
                  AND companies.status = 'ACTIVE'
            """),
            {"token_hash": hash_token(credentials.credentials)},
        ).mappings().first()

    if user is None:
        raise HTTPException(401, "Your token is invalid or has expired. Please log in again.")

    return dict(user)


def allow_roles(*roles):
    """Only let users with one of these roles use the endpoint, otherwise return 403.

    Usage in an endpoint:
        user = Depends(allow_roles(ADMIN, MANAGER))
    """
    def check_role(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "You do not have permission to do this.")
        return user

    return check_role
