"""Creates the database tables.

It runs every .sql file in the migrations folder, in number order.
Each file is remembered in the schema_migrations table, so it only ever runs once.

Usage:  python migrate.py
"""
from pathlib import Path

from sqlalchemy import text

from app.database import get_engine

MIGRATIONS_FOLDER = Path(__file__).resolve().parent / "migrations"


def run_migrations(engine):
    # This table remembers which migration files already ran.
    with engine.begin() as db:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name VARCHAR(255) PRIMARY KEY,
                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        already_applied = set(db.execute(text("SELECT name FROM schema_migrations")).scalars())

    # sorted() puts 001_..., 002_..., 003_... in the right order.
    for sql_file in sorted(MIGRATIONS_FOLDER.glob("*.sql")):
        if sql_file.name in already_applied:
            continue

        print(f"Running {sql_file.name}")
        sql = sql_file.read_text(encoding="utf-8")

        with engine.begin() as db:
            # MySQL can only run one statement at a time, so split the file on ";".
            for statement in sql.split(";"):
                if statement.strip():
                    db.execute(text(statement))

            db.execute(
                text("INSERT INTO schema_migrations (name) VALUES (:name)"),
                {"name": sql_file.name},
            )


if __name__ == "__main__":
    run_migrations(get_engine())
    print("Database is up to date.")
