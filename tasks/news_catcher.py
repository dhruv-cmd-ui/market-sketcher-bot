"""Task 1: Event-Driven News Catcher.

Polls official RSS feeds between 06:00 and 23:00 IST and posts the best new item
(SEBI first, then newest) as a still card to Telegram and an animated Reel to
Instagram + Facebook. Pacing: MAX_NEWS_PER_RUN per check, MAX_NEWS_PER_DAY per day,
and items older than NEWS_MAX_AGE_HOURS are skipped.
"""
import calendar
import datetime
import html
import logging
import time

import config
import feeds
import gemini_client
import history_store
import backgrounds
import image_render
import reel_render
from multi_publish import post_card_to_telegram, post_reel_to_meta

logger = logging.getLogger(__name__)


def _card_meta(link: str) -> tuple[str, str]:
    if "sebi.gov.in" in link:
        return "SEBI UPDATE", "SEBI"
    if "economictimes" in link:
        return "MARKET UPDATE", "ET Markets"
    return "MARKET UPDATE", "News"


def _date_only(entry) -> datetime.datetime | None:
    """SEBI publishes dates like '16 Oct, 2026 +0530' that feedparser can't parse."""
    raw = (getattr(entry, "published", "") or "").strip()
    try:
        return datetime.datetime.strptime(raw, "%d %b, %Y %z")
    except ValueError:
        return None


def _published_date(entry) -> datetime.date:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed:
        return datetime.date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)
    day = _date_only(entry)
    return day.date() if day else datetime.datetime.now(config.IST).date()


def _published_ts(entry) -> float | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed:
        return calendar.timegm(parsed)  # feedparser normalizes to UTC
    day = _date_only(entry)
    # Date without a time: treat it as the end of that day, so yesterday's
    # evening items still count as fresh at 6 AM but older ones don't.
    return (day + datetime.timedelta(hours=23, minutes=59)).timestamp() if day else None


def _collect_candidates() -> list:
    """New entries, best first: earlier feeds in RSS_FEEDS win, then newest first.
    Entries older than NEWS_MAX_AGE_HOURS are marked processed and dropped."""
    now = time.time()
    candidates, stale = [], 0
    for priority, feed_url in enumerate(config.RSS_FEEDS):
        try:
            parsed = feeds.fetch(feed_url)
        except Exception:
            logger.exception("Failed to parse RSS feed: %s", feed_url)
            continue
        if parsed.bozo and not parsed.entries:
            logger.warning("Feed returned no usable entries: %s", feed_url)
            continue

        for position, entry in enumerate(parsed.entries):
            link = getattr(entry, "link", None)
            if not link or history_store.is_news_processed(link):
                continue
            ts = _published_ts(entry)
            # Entries with no readable date at all are treated as fresh.
            if ts is not None and now - ts > config.NEWS_MAX_AGE_HOURS * 3600:
                history_store.mark_news_processed(link)
                stale += 1
                continue
            # Feeds list newest first, so position breaks ties for undated items.
            candidates.append((priority, -(ts or now), position, entry))
    if stale:
        logger.info("News Catcher: skipped %d item(s) older than %.0fh.", stale, config.NEWS_MAX_AGE_HOURS)
    candidates.sort(key=lambda c: c[:3])
    return [c[3] for c in candidates]


def _process_entry(entry) -> bool:
    """Posts one item; returns True if the Telegram card went out."""
    link = entry.link
    title = html.unescape(getattr(entry, "title", "")).strip()
    summary = html.unescape(getattr(entry, "summary", "")).strip()
    context = f"Headline: {title}\nSummary: {summary}\nSource URL: {link}"

    header, source = _card_meta(link)
    try:
        content = gemini_client.generate_content(context)
    except Exception:
        logger.warning("Gemini captions unavailable; using template captions.", exc_info=True)
        content = {
            "telegram_caption": f"{header.title()}: {title}\n\nRead more: {link}",
            "social_caption": f"{title}\n\n#StockMarket #IndianStockMarket #Nifty #Sensex #{source.replace(' ', '')}",
        }
    date = _published_date(entry)
    background = backgrounds.get_background(title or link)
    local_path = image_render.render_news_card(header, title, source, date, background)

    if not post_card_to_telegram(local_path, content["telegram_caption"]):
        logger.warning("Telegram post failed for %s; will retry next cycle.", link)
        return False
    history_store.mark_news_processed(link)
    logger.info("News item processed and marked: %s", link)

    # The Reel (Instagram + Facebook only) must never affect the Telegram card post.
    try:
        reel_path = reel_render.render_news_reel(header, title, source, date, background[0])
        logger.info("News reel rendered at %s", reel_path)
        post_reel_to_meta(reel_path, content["social_caption"])
    except Exception:
        logger.warning("News reel render/post failed for %s.", link, exc_info=True)
    return True


def run() -> None:
    now = datetime.datetime.now(config.IST)
    if not (config.NEWS_WINDOW_START_HOUR <= now.hour < config.NEWS_WINDOW_END_HOUR):
        return
    today = now.date().isoformat()
    remaining = config.MAX_NEWS_PER_DAY - history_store.daily_count("news_posted", today)
    if remaining <= 0:
        logger.info("News Catcher: daily cap of %d posts reached.", config.MAX_NEWS_PER_DAY)
        return

    logger.info("News Catcher: checking feeds...")
    candidates = _collect_candidates()
    if not candidates:
        logger.info("News Catcher: no new items.")
        return

    for entry in candidates[: min(config.MAX_NEWS_PER_RUN, remaining)]:
        try:
            if _process_entry(entry):
                history_store.increment_daily_count("news_posted", today)
        except Exception:
            logger.exception("News Catcher: failed to process entry %s", getattr(entry, "link", "?"))
