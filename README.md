# Multi-Tenant SaaS CRM

A standalone backend for the Multi-Tenant SaaS CRM engineering assessment.
The intended system manages company users, leads, contacts, customers, deals,
activities and notes, with tenant isolation and role-based access.

## Implementation status

The project is in its initial setup stage. Currently implemented: the FastAPI
application, a health endpoint and generated API documentation. Database integration,
authentication, tenant isolation and CRM features are pending. This is not yet a
complete assessment submission.

## Technology choices

- Python and FastAPI: request handling, validation and generated OpenAPI documentation.
- Uvicorn: the server that runs the FastAPI application.
- MySQL (planned): relational storage for CRM data.
- SQLAlchemy and Alembic (planned): database access and versioned schema migrations.
- pytest (planned): automated tests.

Python was selected for familiarity and maintainability. FastAPI supports documented
REST endpoints, and MySQL supports the relationships and transactions needed by the CRM.

## Architecture

Currently, `main.py` contains the application and its health route. The planned
structure separates API routes, request validation, business logic and database models
as those components are implemented. Endpoints use the `/api/v1` prefix.

## Database design

Database models, migrations and the ERD are pending. Planned tables include companies,
users, plans, subscriptions, leads, contacts, customers, deals, activities, notes and
audit logs. Tenant-owned records will be associated with a company.

## Installation and running locally

Prerequisite: Python 3.10 or newer; the initial setup was verified with Python 3.14.
MySQL is not required for the current health endpoint.

From PowerShell in the repository folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

If `.venv` already exists, skip the first command. No environment activation
is needed because these commands use its Python directly. Keep the server terminal
running while using the API. Wait for Uvicorn to report that it is running at
`http://127.0.0.1:8000` before opening the links below.

Open http://127.0.0.1:8000/api/v1/health to see:

```json
{"status": "ok"}
```

Open http://127.0.0.1:8000/docs to try the endpoint from the interactive API
documentation. Stop the server with Ctrl+C.

If the browser reports `ERR_CONNECTION_REFUSED`, check that the server is still
running and inspect its terminal for startup errors.

## API documentation

- Swagger UI: http://127.0.0.1:8000/docs
- OpenAPI schema: http://127.0.0.1:8000/openapi.json
- `GET /api/v1/health`: returns HTTP 200 with `{"status": "ok"}`. This checks API
  availability only, not database connectivity. It requires no authentication.

Authentication, request bodies and error responses for CRM endpoints will be
documented as those endpoints are implemented.

## Testing

An automated test suite is pending. To manually verify the running application:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

Expected result: `status` is `ok`. The planned suite will cover authentication,
tenant isolation, permissions, lead operations, conversion concurrency and plan limits.

## Security considerations

Security controls for the CRM are pending. Planned controls include authenticated
tenant context, role and record permissions, protection of company and role fields,
password hashing, input validation and login rate limiting. Tenant restrictions must
also apply to search, dashboards, audit logs and background jobs.

## Scaling considerations

The intended design will use tenant-aware indexes, bounded pagination and efficient
relationship loading. Background work will use a queue. Index choices, caching and
further scaling options will be documented alongside the implemented queries.

## Major design decisions

- API versioning starts at `/api/v1`; future incompatible changes will use a separate version.
- MySQL is the intended database; no database has been connected yet.
- Lead conversion will require a transaction and database uniqueness safeguards to
  prevent duplicate customers under concurrent requests. Implementation is pending.

## Remaining deliverables

CRM source code, migrations, seed data for at least two companies, automated tests
and architecture documentation including an ERD remain to be implemented.
Docker Compose configuration is planned. The completed application must run without
access to private company infrastructure.
