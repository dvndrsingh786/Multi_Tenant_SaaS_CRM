"""Turns errors into clean JSON responses.

We never send Python stack traces or database messages to the client,
because they can reveal how the system works inside.
"""
import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("crm")


def add_error_handlers(app):

    # 422: the request data is wrong. We list each bad field with a message.
    @app.exception_handler(RequestValidationError)
    def validation_error(request: Request, error: RequestValidationError):
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
