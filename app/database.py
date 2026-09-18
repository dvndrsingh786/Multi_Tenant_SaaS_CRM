import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine

# Read the settings from the .env file in the project folder.
# (Inside Docker there is no .env file; the settings come from docker-compose.yml.)
PROJECT_FOLDER = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_FOLDER / ".env")


# @lru_cache means this function only really runs once.
# After that it returns the same engine, so the whole app shares one connection pool.
@lru_cache
def get_engine():
    # Stop with a clear message if a required setting is missing.
    for setting in ["DB_NAME", "DB_USER", "DB_PASSWORD"]:
        if not os.getenv(setting):
            raise ValueError(f"Set {setting} in your .env file.")

    # URL.create handles special characters in the password for us.
    database_url = URL.create(
        drivername="mysql+pymysql",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.environ["DB_NAME"],
        query={"charset": "utf8mb4"},
    )

    return create_engine(
        database_url,
        pool_pre_ping=True,  # check a saved connection still works before using it
        # Store and compare all times in UTC so there is no time zone confusion.
        connect_args={"init_command": "SET time_zone = '+00:00'"},
    )
