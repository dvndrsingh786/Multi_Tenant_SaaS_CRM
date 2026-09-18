from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database import create_database_engine


def main():
    # Prepare the connection using our .env settings.
    try:
        engine = create_database_engine()
    except ValueError as error:
        raise SystemExit(f"Configuration error: {error}") from None

    try:
        # Open a connection, run a simple SQL query, then close the connection.
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("MySQL connection successful.")
    except SQLAlchemyError:
        raise SystemExit(
            "Cannot connect to MySQL. Check the service, database name, credentials and permissions."
        ) from None
    finally:
        # Release any connections kept by this short-lived script.
        engine.dispose()


if __name__ == "__main__":
    main()
