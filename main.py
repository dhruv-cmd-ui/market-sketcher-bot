"""Entrypoint: configure logging and start the scheduler."""
import logging
from logging.handlers import RotatingFileHandler

import config
from scheduler import build_scheduler


def _configure_logging() -> None:
    handlers = [
        logging.StreamHandler(),
        RotatingFileHandler(config.LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=handlers,
    )


def main() -> None:
    _configure_logging()
    logger = logging.getLogger(__name__)

    scheduler = build_scheduler()
    for job in scheduler.get_jobs():
        # Before scheduler.start(), APScheduler hasn't computed next_run_time
        # for every job yet (it's an unset slot, not None) -- guard with getattr.
        next_run = getattr(job, "next_run_time", None) or "pending (computed at scheduler start)"
        logger.info("Scheduled job '%s' -> next run at %s", job.id, next_run)

    logger.info("Starting scheduler. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down.")


if __name__ == "__main__":
    main()
