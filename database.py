import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine

# Read the connection settings from the .env file beside this file.
load_dotenv(Path(__file__).with_name(".env"))


def create_database_engine():
    # Stop with a clear message if a required setting is missing.
    required_settings = ("DB_NAME", "DB_USER", "DB_PASSWORD")
    for setting in required_settings:
        if not os.getenv(setting):
            raise ValueError(f"Set {setting} in your local .env file.")

    # Build the connection address. URL.create handles special characters in passwords.
    database_url = URL.create(
        drivername="mysql+pymysql",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.environ["DB_NAME"],
        query={"charset": "utf8mb4"},
    )

    # The engine manages connections. It connects when we call engine.connect().
    return create_engine(
        database_url,
        pool_pre_ping=True,  # Check that reused connections are still working.
        connect_args={"connect_timeout": 5},
    )
