"""Fan-out helpers: still cards go to Telegram, Reels/Posts go to Instagram +
Facebook, the FII/DII Reel also goes to YouTube Shorts.

Each platform failure is logged and swallowed so one broken platform (e.g.
Meta before app review is complete) never blocks the others.
"""
import datetime
import logging

import config
import history_store
import image_host
import market_calendar
from publishers import meta_photos, meta_reels, telegram, youtube

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
    """On NSE trading days, hold one Meta slot back for FII/DII's Reel until it has
    posted or its window has closed. Weekends and NSE holidays publish no FII/DII
    data, so no hold."""
    if history_store.get_value("last_fii_dii_post_date") == now.date().isoformat():
        return False
    if now.hour >= config.FII_WINDOW_END_HOUR:
        return False
    return market_calendar.is_trading_day(now.date())


def reels_left(kind: str = "news") -> int:
    """Meta post slots (Reels + Image Posts combined) still allowed today for this
    kind ("news" or "fii") -- a generous safety ceiling; day-to-day volume is
    actually set by the fixed news windows below and FII/DII's once-a-day post."""
    now = datetime.datetime.now(config.IST)
    used = history_store.daily_count("reels_posted", now.date().isoformat())
    limit = config.MAX_REELS_PER_DAY
    if kind == "news" and _fii_slot_reserved(now):
        limit -= 1
    return max(0, limit - used)


# (window start hour, end hour, "reel"/"post", history_store key for "already used today")
if config.META_FULL_SCHEDULE:
    _NEWS_META_WINDOWS = [
        (8, config.NEWS_MORNING_REEL_END_HOUR + 1, "reel", "news_morning_reel_date"),
        (config.NEWS_AFTERNOON_POST_START_HOUR, config.NEWS_AFTERNOON_POST_END_HOUR, "post", "news_afternoon_post_date"),
        (config.NEWS_EVENING_REEL_START_HOUR, config.NEWS_EVENING_REEL_END_HOUR, "reel", "news_evening_reel_date"),
    ]
else:
    _NEWS_META_WINDOWS = [
        (config.NEWS_MORNING_REEL_START_HOUR, config.NEWS_MORNING_REEL_END_HOUR, "post", "news_morning_reel_date"),
    ]


def news_meta_action() -> tuple[str, str] | None:
    """Returns ("reel"|"post", window_key) if now falls inside one of the fixed daily
    news windows and that window hasn't posted yet today, else None. Whichever news
    item the News Catcher is already processing this cycle (already the best-ranked
    one, trending-boosted) is what gets posted -- there's no separate re-pick here."""
    now = datetime.datetime.now(config.IST)
    today = now.date().isoformat()
    for start, end, kind, key in _NEWS_META_WINDOWS:
        if start <= now.hour < end and history_store.get_value(key) != today:
            return kind, key
    return None


def mark_news_meta_slot_used(window_key: str) -> None:
    history_store.set_value(window_key, datetime.datetime.now(config.IST).date().isoformat())


def post_reel_to_meta(local_video_path: str, caption: str, kind: str = "news") -> bool:
    """Returns True if the reel posted to at least one platform."""
    if not meta_configured():
        logger.info("Meta credentials not set; reel saved at %s but not posted.", local_video_path)
        return False
    today = datetime.datetime.now(config.IST).date().isoformat()
    if reels_left(kind) <= 0:
        logger.info("No %s Meta slots left today (cap %d); reel saved at %s but not posted.",
                    kind, config.MAX_REELS_PER_DAY, local_video_path)
        return False
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
        if kind == "news":
            history_store.increment_daily_count("news_reels_posted", today)
    return posted


def post_photo_to_meta(local_image_path: str, caption: str, kind: str = "news") -> bool:
    """Image Post: the same locally-rendered card already sent to Telegram, with the
    same Gemini-generated caption/keywords as a Reel would get. Returns True if the
    photo posted to at least one platform."""
    if not meta_configured():
        logger.info("Meta credentials not set; photo saved at %s but not posted.", local_image_path)
        return False
    today = datetime.datetime.now(config.IST).date().isoformat()
    if reels_left(kind) <= 0:
        logger.info("No %s Meta slots left today (cap %d); photo saved at %s but not posted.",
                    kind, config.MAX_REELS_PER_DAY, local_image_path)
        return False
    posted = False
    if config.FB_PAGE_ID:
        try:
            media_id = meta_photos.post_facebook_photo(local_image_path, caption)
            posted = True
            logger.info("Posted photo to Facebook (id %s).", media_id)
        except Exception:
            logger.warning("Facebook photo post failed.", exc_info=True)
    if config.IG_USER_ID:
        public_url = image_host.publish_public_copy(local_image_path)
        if public_url is None:
            logger.warning("No public URL available; Instagram photo post skipped.")
        else:
            try:
                media_id = meta_photos.post_instagram_photo(public_url, caption)
                posted = True
                logger.info("Posted photo to Instagram (id %s).", media_id)
            except Exception:
                logger.warning("Instagram photo post failed.", exc_info=True)
    if posted:
        history_store.increment_daily_count("reels_posted", today)
    return posted


def youtube_configured() -> bool:
    return bool(config.YOUTUBE_CLIENT_ID and config.YOUTUBE_CLIENT_SECRET and config.YOUTUBE_REFRESH_TOKEN)


def post_video_to_youtube(local_video_path: str, title: str, description: str, tags: list[str],
                          thumbnail_path: str | None = None) -> None:
    """Independent of the Meta Reel/Post budget -- YouTube has its own separate quota."""
    if not youtube_configured():
        logger.info("YouTube credentials not set; video saved at %s but not posted.", local_video_path)
        return
    try:
        video_id = youtube.upload_short(local_video_path, title, description, tags)
        logger.info("Posted Short to YouTube (id %s).", video_id)
    except Exception:
        logger.warning("YouTube upload failed.", exc_info=True)
        return
    if thumbnail_path:
        try:
            youtube.set_thumbnail(video_id, thumbnail_path)
        except Exception:
            # Needs a phone-verified channel; failing here must not affect the upload itself.
            logger.warning("YouTube thumbnail set failed (channel may need phone verification).", exc_info=True)
