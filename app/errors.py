"""Turns errors into clean JSON responses.

We never send Python stack traces or database messages to the client,
because they can reveal how the system works inside.
"""
import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("crm")


# ---------- What errors look like (used in the API documentation) ----------

class ErrorResponse(BaseModel):
    detail: str


class FieldError(BaseModel):
    field: str
    message: str


class ValidationErrorResponse(BaseModel):
    detail: str
    errors: list[FieldError]


# Added to every router in main.py, so /docs shows the possible errors for each endpoint.
ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "The request body is not valid JSON"},
    401: {"model": ErrorResponse, "description": "Not logged in, or the token is invalid/expired"},
    403: {"model": ErrorResponse, "description": "Your role is not allowed to do this, or a plan limit was reached"},
    404: {"model": ErrorResponse, "description": "Not found (also used for records of other companies)"},
    409: {"model": ErrorResponse, "description": "Conflict, e.g. duplicate email or lead already converted"},
    422: {"model": ValidationErrorResponse, "description": "Invalid input, with one message per field"},
    429: {"model": ErrorResponse, "description": "Too many requests (rate limit)"},
    500: {"model": ErrorResponse, "description": "Unexpected server error (no internal details are shown)"},
}


def add_error_handlers(app):

    # 422: the request data is wrong. We list each bad field with a message.
    @app.exception_handler(RequestValidationError)
    def validation_error(request: Request, error: RequestValidationError):
        # 400: the body is not even valid JSON (for example a missing quote or bracket).
        if any(item["type"] == "json_invalid" for item in error.errors()):
            return JSONResponse(status_code=400, content={"detail": "The request body is not valid JSON."})

        errors = []
        for item in error.errors():
            # item["loc"] looks like ("body", "email") or ("query", "per_page").
            # We drop the first part so the client just sees "email" or "per_page".
            field = ".".join(str(part) for part in item["loc"][1:])
            errors.append({"field": field, "message": item["msg"]})
        # We do not echo back the submitted values, so passwords never appear in responses.
        return JSONResponse(status_code=422, content={"detail": "Validation failed.", "errors": errors})

    # 409: the database refused the change, for example a duplicate unique value.
    @app.exception_handler(IntegrityError)
    def integrity_error(request: Request, error: IntegrityError):
        logger.warning("Integrity error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=409, content={"detail": "This conflicts with existing data."})

    # 500: anything we did not expect. Log the details for us, send a short message to the client.
    @app.exception_handler(Exception)
    def unexpected_error(request: Request, error: Exception):
        logger.exception("Unexpected error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})
