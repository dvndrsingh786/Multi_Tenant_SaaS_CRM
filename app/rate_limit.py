"""Simple rate limiting, stored in MySQL.

Each key (for example "login:<ip address>:<email>") has a counter that resets every minute.
Because the counter lives in the database, it works even if we run several copies of the API.
"""
import hashlib

from fastapi import HTTPException
from sqlalchemy import text


def check_rate_limit(engine, key, max_requests, window_seconds=60):
    bucket_key = hashlib.sha256(key.encode()).hexdigest()

    with engine.begin() as db:
        # Make sure a row exists for this key. INSERT IGNORE does nothing if it already exists.
        db.execute(
            text("INSERT IGNORE INTO rate_limits (bucket_key, hits, expires_at) "
                 "VALUES (:key, 0, UTC_TIMESTAMP())"),
            {"key": bucket_key},
        )

        # FOR UPDATE locks the row, so two requests at the same time cannot both read the old count.
        row = db.execute(
            text("SELECT hits, expires_at <= UTC_TIMESTAMP() AS expired "
                 "FROM rate_limits WHERE bucket_key = :key FOR UPDATE"),
            {"key": bucket_key},
        ).mappings().one()

        if row["expired"]:
            # The last window is over, start a new one.
            hits = 1
            db.execute(
                text("UPDATE rate_limits SET hits = 1, "
                     "expires_at = DATE_ADD(UTC_TIMESTAMP(), INTERVAL :seconds SECOND) "
                     "WHERE bucket_key = :key"),
                {"key": bucket_key, "seconds": window_seconds},
            )
        else:
            hits = row["hits"] + 1
            db.execute(
                text("UPDATE rate_limits SET hits = hits + 1 WHERE bucket_key = :key"),
                {"key": bucket_key},
            )

    if hits > max_requests:
        raise HTTPException(
            429,
            "Too many requests. Please wait a minute and try again.",
            headers={"Retry-After": str(window_seconds)},
        )
