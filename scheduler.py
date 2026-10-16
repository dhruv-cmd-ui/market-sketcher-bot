"""APScheduler job registration: news, FII/DII and daily media cleanup."""
import datetime
import logging

from apscheduler.schedulers.blocking import BlockingScheduler

import config
import housekeeping
from tasks import fii_dii_monitor, news_catcher

logger = logging.getLogger(__name__)


def _run_safely(name: str, func) -> None:
    try:
        func()
    except Exception:
        logger.exception("Unhandled error in job '%s'", name)


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone=config.IST)

    scheduler.add_job(
        lambda: _run_safely("news_catcher", news_catcher.run),
        trigger="interval",
        minutes=30,
        id="news_catcher",
        max_instances=1,
        misfire_grace_time=300,
        next_run_time=datetime.datetime.now(config.IST),
    )

    scheduler.add_job(
        lambda: _run_safely("fii_dii_monitor", fii_dii_monitor.run),
        trigger="cron",
        day_of_week="mon-fri",
        hour="17-21",
        minute="*/15",
        id="fii_dii_monitor",
        max_instances=1,
        misfire_grace_time=120,
    )

    scheduler.add_job(
        lambda: _run_safely("housekeeping", housekeeping.prune_media),
        trigger="cron",
        hour=3,
        minute=30,
        id="housekeeping",
        max_instances=1,
        misfire_grace_time=3600,
    )

    return scheduler
