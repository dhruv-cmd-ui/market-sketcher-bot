"""Fan-out helpers: still cards go to Telegram, Reels go to Instagram + Facebook.

Each platform failure is logged and swallowed so one broken platform (e.g.
Meta before app review is complete) never blocks the others.
"""
import datetime
import logging

import config
import history_store
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


def post_reel_to_meta(local_video_path: str, caption: str) -> None:
    if not meta_configured():
        logger.info("Meta credentials not set; reel saved at %s but not posted.", local_video_path)
        return
    today = datetime.datetime.now(config.IST).date().isoformat()
    if history_store.daily_count("reels_posted", today) >= config.MAX_REELS_PER_DAY:
        logger.info("Daily reel cap (%d) reached; reel saved at %s but not posted.",
                    config.MAX_REELS_PER_DAY, local_video_path)
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
