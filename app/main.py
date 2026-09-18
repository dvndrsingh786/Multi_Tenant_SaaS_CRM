import logging

from fastapi import FastAPI

from app.errors import add_error_handlers
from app.routers import activities, auth, company, contacts, customers, deals, leads, reports, users

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Multi-Tenant SaaS CRM API",
    version="1.0.0",
    description="A CRM where many companies share one system, but each company only sees its own data.",
)

add_error_handlers(app)

app.include_router(auth.router)
app.include_router(company.router)
app.include_router(users.router)
app.include_router(leads.router)
app.include_router(customers.router)
app.include_router(contacts.router)
app.include_router(deals.router)
app.include_router(activities.router)
app.include_router(reports.router)


@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
