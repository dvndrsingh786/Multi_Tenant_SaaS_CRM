"""Shared test setup.

The tests never touch your real database. At the start we create a brand new
database called crm_test_<random>, run all migrations on it, and delete it at the end.
Before every test we empty all the tables, so each test starts from a clean state.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.database import get_engine
from app.main import app
from migrate import run_migrations

# Tables that keep their rows between tests (plans are fixed data from a migration).
TABLES_TO_KEEP = {"plans", "schema_migrations"}


@pytest.fixture(scope="session")
def test_engine():
    main_engine = get_engine()
    test_database_name = "crm_test_" + uuid4().hex[:12]

    with main_engine.begin() as db:
        db.execute(text(f"CREATE DATABASE `{test_database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))

    engine = create_engine(
        main_engine.url.set(database=test_database_name),
        connect_args={"init_command": "SET time_zone = '+00:00'"},
    )
    run_migrations(engine)

    yield engine

    engine.dispose()
    with main_engine.begin() as db:
        db.execute(text(f"DROP DATABASE `{test_database_name}`"))


@pytest.fixture(autouse=True)
def clean_tables(test_engine):
    with test_engine.begin() as db:
        table_names = db.execute(text("SHOW TABLES")).scalars().all()
        db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table_name in table_names:
            if table_name not in TABLES_TO_KEEP:
                db.execute(text(f"TRUNCATE TABLE `{table_name}`"))
        db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


@pytest.fixture
def client(test_engine):
    # Tell FastAPI: "whenever an endpoint asks for get_engine, give it the test database".
    app.dependency_overrides[get_engine] = lambda: test_engine
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
