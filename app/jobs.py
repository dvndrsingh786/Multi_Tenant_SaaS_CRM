"""Background jobs. They are run by worker.py, not by the API.

1. send_activity_reminders: for every unfinished activity that is due in the next hour,
   save a notification for the user who owns it (and write it to the log).
2. clean_up_expired_rows: delete login tokens and rate-limit counters that have expired.

What if a job fails halfway? Nothing is lost:
- each reminder is saved in its own small transaction,
- notifications.activity_id is UNIQUE and we use INSERT IGNORE,
so the next run (one minute later) just picks up whatever was not done yet,
and it can never send the same reminder twice.
"""
import logging

from sqlalchemy import text

logger = logging.getLogger("crm.jobs")

REMIND_MINUTES_BEFORE = 60


def send_activity_reminders(engine):
    with engine.connect() as db:
        # LEFT JOIN + "notifications.id IS NULL" means: activities that have no reminder yet.
        due_activities = db.execute(
            text("""
                SELECT activities.id, activities.company_id, activities.user_id,
                       activities.title, activities.due_at
                FROM activities
                LEFT JOIN notifications ON notifications.activity_id = activities.id
                WHERE activities.completed_at IS NULL
                  AND activities.due_at BETWEEN UTC_TIMESTAMP()
                      AND DATE_ADD(UTC_TIMESTAMP(), INTERVAL :minutes MINUTE)
                  AND notifications.id IS NULL
                LIMIT 1000
            """),
            {"minutes": REMIND_MINUTES_BEFORE},
        ).mappings().all()

    sent = 0
    for activity in due_activities:
        message = f"Reminder: '{activity['title']}' is due at {activity['due_at']:%Y-%m-%d %H:%M} UTC."
        with engine.begin() as db:
            result = db.execute(
                text("""
                    INSERT IGNORE INTO notifications (company_id, user_id, activity_id, message)
                    VALUES (:company_id, :user_id, :activity_id, :message)
                """),
                {"company_id": activity["company_id"], "user_id": activity["user_id"],
                 "activity_id": activity["id"], "message": message},
            )
        # rowcount is 0 when the reminder already existed (another worker was faster).
        if result.rowcount == 1:
            sent += 1
            # A real system would send an email or push message here. The brief allows logging it.
            logger.info("Reminder for user %s: %s", activity["user_id"], message)

    return sent


def clean_up_expired_rows(engine):
    with engine.begin() as db:
        db.execute(text("DELETE FROM auth_tokens WHERE expires_at < UTC_TIMESTAMP()"))
        db.execute(text("DELETE FROM rate_limits WHERE expires_at < UTC_TIMESTAMP()"))
