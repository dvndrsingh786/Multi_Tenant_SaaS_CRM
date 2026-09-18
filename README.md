# Multi-Tenant SaaS CRM (Backend)

A backend API for a CRM that many companies use at the same time. Each company
manages its own users, leads, contacts, customers, deals and activities, and
**a company can never see or change another company's data**.

Built with **Python, FastAPI and MySQL**.

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (architecture, ERD, scaling, API v2 plan).

---

## Contents

1. [Features](#features)
2. [Technology choices](#technology-choices)
3. [Project structure](#project-structure)
4. [How to run it](#how-to-run-it)
5. [How to run the tests](#how-to-run-the-tests)
6. [API documentation](#api-documentation)
7. [Roles and permissions](#roles-and-permissions)
8. [How tenant isolation works](#how-tenant-isolation-works)
9. [Lead conversion and concurrency](#lead-conversion-and-concurrency)
10. [Security](#security)
11. [Database design](#database-design)
12. [Performance and scaling](#performance-and-scaling)
13. [API versioning](#api-versioning)
14. [Design decisions and assumptions](#design-decisions-and-assumptions)

---

## Features

- Register a company (the person who registers becomes its ADMIN), login, logout, "me"
- Three roles: ADMIN, MANAGER, SALES_AGENT, checked on every endpoint
- Users, leads, contacts, customers, deals (with pipeline stages), activities and lead notes
- Lead list with pagination, search, filters and sorting
- Lead assignment and **lead → customer conversion** (safe against double requests)
- Dashboard with totals and pipeline value
- Global search across leads, contacts, customers and deals
- Audit log for CREATE, UPDATE, DELETE, LOGIN, LOGOUT, ASSIGN and CONVERT
- Subscription plans (FREE / STARTER / PRO / ENTERPRISE) with user and lead limits
- Background worker that creates reminders for activities that are due soon
- Rate limiting on login and register
- 130+ automated tests, seed data for two companies, Docker setup

## Technology choices

| Tool | Why I chose it |
| --- | --- |
| **Python + FastAPI** | Short, readable code. FastAPI checks request data with Pydantic and creates the Swagger docs automatically. |
| **MySQL 8 (InnoDB)** | Supports transactions, foreign keys and row locks (`SELECT ... FOR UPDATE`), which this project needs. |
| **SQLAlchemy Core with plain SQL** | I write the SQL myself with `text()` and named parameters (`:company_id`). The parameters protect against SQL injection, and every query is easy to read and to check for the company filter. |
| **Numbered `.sql` migration files** | Each table is a plain SQL file that is easy to review. `migrate.py` runs each file once. |
| **pwdlib (Argon2)** | Argon2 is a slow, salted hashing algorithm made for passwords. |
| **pytest + TestClient** | Tests call the real API against a real temporary MySQL database. |
| **Docker Compose** | Starts MySQL, the API and the worker with one command. |

The brief prefers Laravel/PHP, but it allows Python/FastAPI. I chose Python because it is
the language I know best, so I can explain every line.

## Project structure

```
app/
  main.py            creates the FastAPI app and adds all routers
  database.py        MySQL connection (reads .env)
  security.py        password hashing, tokens, get_current_user, allow_roles
  finders.py         load ONE record safely (company filter + owner filter)
  utils.py           pagination, UPDATE helper, search helper
  plan_limits.py     user/lead limits of the subscription plan
  audit.py           writes rows to audit_logs
  rate_limit.py      rate limiting (stored in MySQL)
  errors.py          clean JSON errors (401/403/404/409/422/429/500)
  jobs.py            background jobs (activity reminders, clean-up)
  routers/           one file per feature: auth, users, leads, customers, deals, ...
  schemas/           Pydantic models: what a request may contain, what a response looks like
migrations/          001_...sql to 014_...sql, one file per table
tests/               automated tests
migrate.py           creates the tables
seed.py              demo data (2 companies)
worker.py            runs the background jobs every minute
docs/                architecture documentation and openapi.json
```

## How to run it

### Option 1: Docker (easiest)

```bash
docker compose up --build
```

This starts MySQL, runs the migrations, adds the demo data, and starts the API and the worker.
Open **http://localhost:8000/docs**.

### Option 2: On your own computer (Windows PowerShell)

You need Python 3.12+ and MySQL 8.

1. Create an empty database:
   ```sql
   CREATE DATABASE multi_tenant_crm CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
2. Copy `.env.example` to `.env` and fill in your MySQL user and password.
3. Install and start:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
   .\.venv\Scripts\python.exe check_database.py      # checks the connection
   .\.venv\Scripts\python.exe migrate.py             # creates the tables
   .\.venv\Scripts\python.exe seed.py                # adds demo data
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
   ```
4. In a second terminal, start the background worker (optional):
   ```powershell
   .\.venv\Scripts\python.exe worker.py
   ```

### Demo users (from `seed.py`)

All passwords are **`Password123!`**

| Company | Admin | Manager | Sales agents |
| --- | --- | --- | --- |
| Acme Ltd | admin@acme.example | manager@acme.example | agent1@acme.example, agent2@acme.example |
| Globex Corp | admin@globex.example | manager@globex.example | agent1@globex.example, agent2@globex.example |

Try logging in as `admin@globex.example` and opening an Acme lead id: you get **404**.

## How to run the tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The tests **never touch your real data**. They create a new database called
`crm_test_<random>`, run all migrations on it, empty the tables before every test,
and delete the database at the end. (So the MySQL user in `.env` needs permission
to create and drop databases.)

With Docker: `docker compose run --rm -e DB_USER=root -e DB_PASSWORD=rootpassword api pytest`

What is tested:

| File | What it checks |
| --- | --- |
| `test_auth.py` | register, login, logout, me, 401s, validation, rate limiting |
| `test_users.py` | roles, no ADMIN escalation, no `company_id` change, tenant isolation, user plan limit |
| `test_company.py` | company settings, plan changes, no downgrade below current usage |
| `test_leads.py` | lead CRUD, search, filters, sorting, pagination, assignment, notes, lead plan limit, tenant isolation |
| `test_conversion.py` | conversion, **double and concurrent conversion**, rollback when a step fails |
| `test_customers.py`, `test_contacts.py`, `test_deals.py`, `test_activities.py` | CRUD, permissions and tenant isolation |
| `test_reports.py` | dashboard numbers, global search, audit logs |
| `test_jobs.py` | reminder job (and that it never sends twice), clean-up job |
| `test_seed.py` | seed data creates two separate companies |

## API documentation

- **Swagger UI:** http://localhost:8000/docs (try every endpoint in the browser)
- **OpenAPI file:** [docs/openapi.json](docs/openapi.json) (can be imported into Postman)

To use protected endpoints: call `POST /api/v1/auth/login`, copy `access_token`, click
**Authorize** in Swagger and paste it. Other clients send the header
`Authorization: Bearer <token>`.

### Endpoints

| Area | Endpoints |
| --- | --- |
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` |
| Company | `GET/PATCH /company`, `GET /plans`, `GET/PATCH /subscription` |
| Users | `GET/POST /users`, `GET/PATCH/DELETE /users/{id}` |
| Leads | `GET/POST /leads`, `GET/PATCH/DELETE /leads/{id}`, `PATCH /leads/{id}/assign`, `POST /leads/{id}/convert`, `GET/POST /leads/{id}/notes` |
| Contacts | `GET/POST /contacts`, `GET/PATCH/DELETE /contacts/{id}` |
| Customers | `GET/POST /customers`, `GET/PATCH/DELETE /customers/{id}` |
| Deals | `GET/POST /deals`, `GET/PATCH/DELETE /deals/{id}`, `PATCH /deals/{id}/stage` |
| Activities | `GET/POST /activities`, `GET/PATCH /activities/{id}` |
| Reports | `GET /dashboard`, `GET /search?q=`, `GET /audit-logs` |
| Notifications | `GET /notifications`, `PATCH /notifications/{id}/read` |

(All paths start with `/api/v1`.)

Example list request:

```
GET /api/v1/leads?page=1&per_page=25&search=john&status=QUALIFIED&source=WEBSITE
    &assigned_to=15&sort_by=created_at&sort_order=desc
```

Every list returns the same shape:

```json
{
  "data": [ ... ],
  "meta": { "page": 1, "per_page": 25, "total": 42, "total_pages": 2 }
}
```

### Errors

| Code | When |
| --- | --- |
| 200 / 201 / 204 | OK / created / deleted (no body) |
| 401 | no token, wrong token, expired token, wrong password |
| 403 | your role is not allowed, or the plan limit is reached |
| 404 | not found, **also for records of another company** |
| 409 | duplicate email, lead already converted, plan downgrade not possible |
| 422 | invalid input. One message per field, for example `{"detail": "Validation failed.", "errors": [{"field": "email", "message": "..."}]}` |
| 429 | too many login/register attempts (`Retry-After: 60`) |
| 500 | unexpected error. Only `"Internal server error."` is sent back, the details go to the server log |

## Roles and permissions

| Action | ADMIN | MANAGER | SALES_AGENT |
| --- | --- | --- | --- |
| Manage users (create, change role, delete) | ✅ | ❌ | ❌ |
| View user list | ✅ | ✅ | only themselves |
| Update company, change plan | ✅ | ❌ | ❌ |
| View / create / update leads | all | all | only assigned to them |
| Delete leads | ✅ | ❌ | ❌ |
| Assign leads | ✅ | ✅ | ❌ |
| Convert a lead, add notes | ✅ | ✅ | own leads |
| View customers | all | all | only assigned |
| Create / update / delete customers | ✅ | ❌ | ❌ |
| Contacts | all | all | only own |
| Deals (incl. stage) | all | all | only own |
| Activities | all | all | only own |
| Dashboard, search | whole company | whole company | only own records |
| Audit logs | ✅ | ❌ | ❌ |

Nobody can create an ADMIN or promote someone to ADMIN through the API. The ADMIN
account cannot be demoted, deactivated or deleted.

## How tenant isolation works

The company is **never** taken from the request. It always comes from the login token:

1. The client sends `Authorization: Bearer <token>`.
2. `get_current_user` (in `app/security.py`) looks up the token hash in `auth_tokens`
   and loads the user **and their `company_id`** from the database.
3. Every SQL query then has `WHERE company_id = :company_id` with that value.
   - Lists build their `WHERE` starting with `company_id = :company_id AND deleted_at IS NULL`.
   - Single records are loaded through `app/finders.py`, which always adds the company
     filter (and `assigned_to = me` / `owner_id = me` for sales agents).
4. A record from another company is simply "not found", so the answer is **404**, not 403.
   That way nobody can even find out that the id exists.
5. The request models reject unknown fields (`extra="forbid"`), so a client cannot send
   `company_id` or `user_id` to move data into another company.
6. **The database helps too:** foreign keys use `(company_id, id)` pairs. For example
   `leads(company_id, assigned_to)` points to `users(company_id, id)`. So MySQL itself
   refuses to assign an Acme lead to a Globex user, even if the code had a bug.

This covers API requests, single records, lists, search, dashboard numbers, notes,
notifications and audit logs.

## Lead conversion and concurrency

`POST /api/v1/leads/{id}/convert` does four things in **one transaction**:
create the customer, mark the lead as converted (`converted_at`, status `WON`),
add an activity, and write the audit log. If any step fails, MySQL undoes all of them
(there is a test that makes the audit log insert fail and checks nothing was saved).

**Two requests at the same time (e.g. a double click):**

1. The lead is loaded with `SELECT ... FOR UPDATE`. This **locks the row**. The second
   request has to wait at that line until the first transaction is finished.
2. When the second request continues, it sees `converted_at` is already set and returns
   **409 Conflict**.
3. **Safety net:** the `customers` table has a `UNIQUE (company_id, lead_id)` key. Even if
   the lock was somehow bypassed, MySQL would refuse a second customer for the same lead,
   and the API would also return 409.

Tests: `test_concurrent_conversions_create_only_one_customer` fires 5 requests at the
same moment (exactly one 201, four 409, one customer), and
`test_second_request_waits_for_the_lock_then_gets_409` shows the lock step by step.

The same idea is used for **plan limits**: the company's subscription row is locked
before counting users/leads, so two requests at the same time cannot both squeeze past
the limit.

## Security

- **Passwords:** hashed with Argon2, never stored or returned in plain text.
- **Tokens:** 32 random bytes. Only the SHA-256 hash is stored, so a leaked database
  cannot be used to log in. Tokens expire after 24 hours. Logout deletes the token.
  Deactivating or deleting a user logs them out everywhere.
- **Login timing:** an unknown email still runs a password check against a fake hash,
  so attackers cannot find out which emails exist by measuring response time.
- **401 / 403:** missing or bad token → 401. Wrong role → 403 (checked before the
  request body is processed).
- **IDOR:** every query is filtered by `company_id` (see above). Other companies' ids → 404.
- **Mass assignment:** every request model uses `extra="forbid"`. Protected fields
  (`company_id`, `user_id`, `lead_id` on customers, `role: ADMIN`) are not in the models.
- **SQL injection:** all values are passed as named parameters. Column names used for
  sorting come from a fixed list (`Literal[...]`), anything else is a 422.
- **LIKE search:** `%` and `_` in search text are escaped.
- **Rate limiting:** login max 5 tries per minute per IP + email, register 10 per minute per IP.
- **Validation:** every field has a type and length limit; `per_page` max 100.
- **Errors:** no stack traces or database messages in responses. The 422 response
  does not echo the submitted values (so passwords never appear in responses).
- **Audit log:** password hashes and tokens are removed before saving old/new values.

## Database design

14 tables, all InnoDB with `utf8mb4_unicode_ci` (case-insensitive search).
The full ERD diagram is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#database-erd).

| Table | Notes |
| --- | --- |
| `companies` | the tenants. Status ACTIVE or SUSPENDED (suspended companies cannot log in) |
| `users` | belongs to a company. Email is unique. Soft delete (`deleted_at`) |
| `plans`, `subscriptions` | 4 plans with limits; one subscription per company |
| `leads`, `contacts`, `customers`, `deals` | all have `company_id`, timestamps and soft delete |
| `activities`, `notes` | linked to leads/customers/deals of the same company |
| `audit_logs` | old/new values stored as JSON |
| `auth_tokens` | SHA-256 hashes of login tokens |
| `rate_limits` | request counters for rate limiting |
| `notifications` | reminders written by the background worker |

Main rules:
- **Every tenant table has `company_id`**, and every index starts with `company_id`
  (e.g. `(company_id, status)`, `(company_id, assigned_to)`), because every query filters by it first.
- **Composite foreign keys** `(company_id, x_id) → other_table(company_id, id)` keep
  links inside one company.
- **Unique keys:** `users.email`, `customers(company_id, lead_id)` (no double conversion),
  `notifications.activity_id` (no double reminder), `subscriptions.company_id`.
- **Soft deletes** for users, leads, contacts, customers and deals, so history and audit
  logs keep working. Activities, notes and audit logs are never deleted.
- **Money** is `DECIMAL(15,2)`, never float. Times are stored in **UTC**.

## Performance and scaling

Full explanation in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#performance-and-scaling). In short:

- **Now:** indexes starting with `company_id`, pagination on every list (max 100 per page),
  no N+1 queries (each list is 2 queries: one COUNT, one page), short transactions.
- **10,000 companies / 1,000,000+ leads:** the company filter reduces each query to one
  company's rows, and the composite indexes make that fast. Deep pages would move to
  "keyset" pagination (`WHERE id < last_id`) instead of large `OFFSET`s.
- **Next steps as it grows:** Redis for rate limiting and caching the dashboard,
  read replicas for lists/search/dashboard, a real queue (Redis + RQ/Celery) for jobs,
  MySQL FULLTEXT or Meilisearch/OpenSearch for search, and finally sharding by `company_id`.

## API versioning

All routes are under `/api/v1`. For a breaking change I would:
1. add new routers under `/api/v2` next to the v1 ones (same database, shared helpers),
2. keep `/api/v1` working unchanged and add a `Deprecation` header to its responses,
3. give clients a clear end date, then remove v1 only when nobody uses it anymore.

Non-breaking changes (a new optional field, a new endpoint) are added to v1 directly.

## Design decisions and assumptions

- **Plain SQL instead of an ORM** so every query, and its `company_id` filter, is visible.
- **Database tokens instead of JWT**, because they can be revoked straight away
  (logout, user deactivated). The price is one small indexed lookup per request.
- **404 for other companies' records** so ids from other tenants are not revealed.
- **Registration** creates the company, the ADMIN and a FREE subscription in one transaction.
- **Email is unique across the whole system**, so login only needs email + password.
  A deleted user's email stays reserved.
- **Only ADMIN manages users.** Managers can see the user list (to assign leads).
- **Customers:** the brief says managers and agents "view" customers, so only ADMIN can
  create/update/delete them. Customers created by conversion keep a link to the lead
  (`lead_id`), and `lead_id` cannot be set by hand.
- **Deal stage** is only changed with `PATCH /deals/{id}/stage` (clear audit trail).
- **Activities** always belong to the user who created them. No DELETE (not in the brief).
- **Converted leads** get status `WON` and a `converted_at` time.
- **Plan limits** count users and leads that are not deleted. Reaching a limit returns 403.
  A downgrade below the current usage returns 409. There is no payment provider (allowed by the brief).
- **Company status** cannot be changed through the API. Suspending a company would be a
  job for a platform super-admin, which is outside this assessment.
- **Rate limits are stored in MySQL** so they work across several API processes. With
  high traffic I would move them to Redis.
