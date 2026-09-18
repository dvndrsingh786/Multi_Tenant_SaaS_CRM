"""The background worker. It runs the jobs in app/jobs.py once every minute.

Usage:
    python worker.py          # run forever
    python worker.py --once   # run the jobs one time and stop
"""
import logging
import sys
import time

from app.database import get_engine
from app.jobs import clean_up_expired_rows, send_activity_reminders

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("crm.worker")

SECONDS_BETWEEN_RUNS = 60


def run_jobs_once(engine):
    sent = send_activity_reminders(engine)
    clean_up_expired_rows(engine)
    logger.info("Jobs finished. Reminders sent: %s", sent)


def main():
    engine = get_engine()

    if "--once" in sys.argv:
        run_jobs_once(engine)
        return

    logger.info("Worker started. Running jobs every %s seconds.", SECONDS_BETWEEN_RUNS)
    while True:
        try:
            run_jobs_once(engine)
        except Exception:
            # If a run fails (for example the database is restarting), we log it and try
            # again next minute instead of crashing the worker.
            logger.exception("Jobs failed. Will try again in %s seconds.", SECONDS_BETWEEN_RUNS)
        time.sleep(SECONDS_BETWEEN_RUNS)


if __name__ == "__main__":
    main()
