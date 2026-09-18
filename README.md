# Multi-Tenant SaaS CRM

A standalone backend for the Multi-Tenant SaaS CRM engineering assessment.
The intended system manages company users, leads, contacts, customers, deals,
activities and notes, with tenant isolation and role-based access.

## Implementation status

The project is in its initial setup stage. Currently implemented: the FastAPI
application, a health endpoint, generated API documentation and a MySQL connection
helper with a command-line check. The connection check has passed against a local
MySQL database. SQL migrations create the `companies` and `users` tables. API database integration,
authentication, tenant isolation and CRM features are pending. This is not yet a
complete assessment submission.

## Technology choices

- Python and FastAPI: request handling, validation and generated OpenAPI documentation.
- Uvicorn: the server that runs the FastAPI application.
- MySQL and PyMySQL: the selected database and its Python connection driver.
- SQLAlchemy: database connection management and future model queries.
- Numbered SQL files: explicit, readable database migrations.
- pytest (planned): automated tests.

Python was selected for familiarity and maintainability. FastAPI supports documented
REST endpoints, and MySQL supports the relationships and transactions needed by the CRM.

## Architecture

Currently, `main.py` contains the application and its health route. The planned
structure separates API routes, request validation, business logic and database models
as those components are implemented. Endpoints use the `/api/v1` prefix.
`database.py` reads local configuration and creates a SQLAlchemy engine;
`check_database.py` verifies connectivity with `SELECT 1` without modifying data.

## Database design

The `companies` table stores each tenant's identity and status:

| Column | Purpose |
| --- | --- |
| id | Automatically generated primary key |
| name | Required company name |
| email, phone, website | Optional company contact information |
| status | ACTIVE (default) or SUSPENDED |
| created_at, updated_at | Creation and last modification times |

The table uses InnoDB to support transactions and future foreign keys. Company names
are not unique because different businesses can share a name.

The `users` table links each user to one company:

| Column | Purpose |
| --- | --- |
| id | Automatically generated primary key |
| company_id | Required foreign key to companies.id; indexed for company queries |
| name, email | Required name and globally unique email |
| password_hash | Stores a password hash, never the original password |
| role | ADMIN, MANAGER or SALES_AGENT (default) |
| status | ACTIVE (default) or INACTIVE |
| created_at, updated_at | Creation and last modification times |

Email uniqueness is case-insensitive under the table collation. This design assumes
one company per user account and supports future login by email without a company
identifier. The foreign key prevents orphan users and blocks deleting a company
that still has users. It does not enforce tenant access permissions by itself;
those checks will be implemented in the API. Password hashing will be implemented
with registration; the database column alone does not hash passwords.

Remaining tables and the full ERD are pending: plans, subscriptions, leads, contacts,
customers, deals, activities, notes and audit logs.

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

## MySQL setup

Use a local MySQL 8 server. Create an empty database using MySQL Workbench or
the MySQL client:

```sql
CREATE DATABASE IF NOT EXISTS multi_tenant_crm
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Copy `.env.example` to `.env` if `.env` does not already exist. Set `DB_USER`
and `DB_PASSWORD` to your local MySQL credentials. The default database name
is `multi_tenant_crm`. Quote passwords in the `.env` file, for example
`DB_PASSWORD='your-password'`. The `.env` file is excluded from Git.
Existing environment variables take precedence over values in this file.

Run the connection check:

```powershell
.\.venv\Scripts\python.exe check_database.py
```

Expected output: `MySQL connection successful.` The check exits with code 1
if configuration or connectivity fails. It does not create tables or a database.
For deployed environments, use a dedicated database account with only the
permissions required by the application.

## Database migrations

SQL migrations are stored in `migrations/` and must be applied once, in numeric
order, to the configured database. Currently there are two migrations.

In MySQL Workbench, select `multi_tenant_crm` as the default schema, open
`migrations/001_create_companies.sql`, and execute it, followed by
`migrations/002_create_users.sql`. Skip migrations already applied. Alternatively, in a MySQL
client session started from the repository folder:

```sql
USE multi_tenant_crm;
SOURCE migrations/001_create_companies.sql;
SOURCE migrations/002_create_users.sql;
```

Verify with `DESCRIBE companies;` and `DESCRIBE users;`. Reapplying a migration reports that the table
already exists; it does not replace existing data. Migration application is currently
manual, without an automatic migration history table. Once applied, preserve this
file and make future schema changes in new numbered migrations.

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
- MySQL connectivity and the companies/users migrations are verified locally; API integration is pending.
- Migrations use SQL files so schema changes can be reviewed directly. Automatic
  migration tracking can be added as the schema grows.
- Lead conversion will require a transaction and database uniqueness safeguards to
  prevent duplicate customers under concurrent requests. Implementation is pending.

## Remaining deliverables

CRM source code, migrations, seed data for at least two companies, automated tests
and architecture documentation including an ERD remain to be implemented.
Docker Compose configuration is planned. The completed application must run without
access to private company infrastructure.
