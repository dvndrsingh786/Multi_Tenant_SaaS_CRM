"""Quick check that the app can connect to MySQL.

Usage:  python check_database.py
"""
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_engine


def main():
    try:
        engine = get_engine()
    except ValueError as error:
        raise SystemExit(f"Configuration error: {error}")

    try:
        with engine.connect() as db:
            db.execute(text("SELECT 1"))
        print("MySQL connection successful.")
    except SQLAlchemyError:
        raise SystemExit("Cannot connect to MySQL. Check that it is running and check your .env settings.")


if __name__ == "__main__":
    main()
