"""Fan-out helpers: still cards go to Telegram, Reels go to Instagram + Facebook.

Each platform failure is logged and swallowed so one broken platform (e.g.
Meta before app review is complete) never blocks the others.
"""
import datetime
import logging

import config
import history_store
import market_calendar
from publishers import meta_reels, telegram

logger = logging.getLogger(__name__)


def post_card_to_telegram(local_image_path: str, caption: str) -> bool:
    try:
        telegram.post(local_image_path, caption)
        logger.info("Posted card to Telegram.")
        return True
    except Exception:
        logger.exception("Telegram post failed.")
        return False


def meta_configured() -> bool:
    return bool(config.META_ACCESS_TOKEN and (config.IG_USER_ID or config.FB_PAGE_ID))


def _fii_slot_reserved(now: datetime.datetime) -> bool:
    """On NSE trading days, hold one Reel back for FII/DII until it has posted or its
    window has closed. Weekends and NSE holidays publish no FII/DII data, so no hold."""
    if history_store.get_value("last_fii_dii_post_date") == now.date().isoformat():
        return False
    if now.hour >= config.FII_WINDOW_END_HOUR:
        return False
    return market_calendar.is_trading_day(now.date())


def reels_left(kind: str = "news") -> int:
    """Reels still allowed today for this kind ("news" or "fii")."""
    now = datetime.datetime.now(config.IST)
    used = history_store.daily_count("reels_posted", now.date().isoformat())
    limit = config.MAX_REELS_PER_DAY
    if kind == "news" and _fii_slot_reserved(now):
        limit -= 1
    return max(0, limit - used)


def post_reel_to_meta(local_video_path: str, caption: str, kind: str = "news") -> None:
    if not meta_configured():
        logger.info("Meta credentials not set; reel saved at %s but not posted.", local_video_path)
        return
    today = datetime.datetime.now(config.IST).date().isoformat()
    if reels_left(kind) <= 0:
        logger.info("No %s Reel slots left today (cap %d); reel saved at %s but not posted.",
                    kind, config.MAX_REELS_PER_DAY, local_video_path)
        return
    posted = False
    for name, func, needed in (("Instagram", meta_reels.post_instagram_reel, config.IG_USER_ID),
                               ("Facebook", meta_reels.post_facebook_reel, config.FB_PAGE_ID)):
        if not needed:
            continue
        try:
            media_id = func(local_video_path, caption)
            posted = True
            logger.info("Posted reel to %s (id %s).", name, media_id)
        except Exception:
            logger.warning("%s reel post failed.", name, exc_info=True)
    if posted:
        history_store.increment_daily_count("reels_posted", today)
