import logging

from fastapi import FastAPI

from app.errors import ERROR_RESPONSES, add_error_handlers
from app.routers import (
    activities, auth, company, contacts, customers, deals, leads, notifications, reports, users,
)

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Multi-Tenant SaaS CRM API",
    version="1.0.0",
    description=(
        "A CRM where many companies share one system, but each company only sees its own data.\n\n"
        "**How to log in:** call `POST /api/v1/auth/login`, copy the `access_token`, click the "
        "**Authorize** button and paste it. Demo users (after `python seed.py`): "
        "`admin@acme.example` / `Password123!`"
    ),
)

add_error_handlers(app)

# ERROR_RESPONSES makes the /docs page list the possible errors for every endpoint.
app.include_router(auth.router, responses=ERROR_RESPONSES)
app.include_router(company.router, responses=ERROR_RESPONSES)
app.include_router(users.router, responses=ERROR_RESPONSES)
app.include_router(leads.router, responses=ERROR_RESPONSES)
app.include_router(customers.router, responses=ERROR_RESPONSES)
app.include_router(contacts.router, responses=ERROR_RESPONSES)
app.include_router(deals.router, responses=ERROR_RESPONSES)
app.include_router(activities.router, responses=ERROR_RESPONSES)
app.include_router(reports.router, responses=ERROR_RESPONSES)
app.include_router(notifications.router, responses=ERROR_RESPONSES)


@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
