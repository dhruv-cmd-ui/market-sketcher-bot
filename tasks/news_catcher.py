"""Task 1: Event-Driven News Catcher.

Polls RSS feeds (SEBI + ET Markets, Mint and Business Standard) between 06:00 and
23:00 IST and posts the best new item as a still card to Telegram and an animated
Reel to Instagram + Facebook.

Selection: SEBI press releases/circulars first (routine enforcement filings are
skipped), then the newest market story from any outlet. A story another outlet
already covered (similar headline) is skipped. Pacing: MAX_NEWS_PER_RUN per check (no
daily cap on Telegram), items older than NEWS_MAX_AGE_HOURS skipped.
"""
import calendar
import datetime
import html
import logging
import re
import time

import config
import feeds
import gemini_client
import history_store
import backgrounds
import image_render
import reel_render
import token_monitor
from multi_publish import (meta_configured, next_meta_action, post_card_to_telegram,
                           post_photo_to_meta, post_reel_to_meta, reels_left)

logger = logging.getLogger(__name__)


_SOURCES = {
    "sebi.gov.in": "SEBI",
    "economictimes.indiatimes.com": "ET Markets",
    "livemint.com": "Mint",
    "business-standard.com": "Business Standard",
}

# SEBI's feed is mostly individual enforcement filings (appeals, recovery and
# attachment notices) that aren't news for followers; press releases and
# circulars are kept.
_ROUTINE_SEBI_TITLE = re.compile(
    r"\b(appeal no|recovery proceedings?|notice of attachment|attachment notice|demand notice|"
    r"recovery certificate|release order|summons|adjudication order|settlement order)\b",
    re.IGNORECASE,
)

_STOPWORDS = set(
    "a an and are as at be by for from has have in into is it its of on or over says the to "
    "up was were will with after amid than this that new rs cr crore lakh per".split()
)


def _card_meta(link: str) -> tuple[str, str]:
    source = next((name for host, name in _SOURCES.items() if host in link), "News")
    return ("SEBI UPDATE" if source == "SEBI" else "MARKET UPDATE"), source


def _is_routine_sebi(link: str, title: str) -> bool:
    return "sebi.gov.in" in link and ("/enforcement/" in link or bool(_ROUTINE_SEBI_TITLE.search(title)))


def _words(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", title.lower()) if len(w) > 2 and w not in _STOPWORDS}


def _same_story(a: set[str], b: set[str]) -> bool:
    """Headlines from different outlets about one story share most of their key words."""
    if min(len(a), len(b)) < 4:
        return False
    return len(a & b) / min(len(a), len(b)) >= 0.6


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
    """New entries, best first: SEBI, then every other feed merged newest first.
    Routine SEBI filings, stale items and stories already posted by another
    outlet are marked processed and dropped."""
    now = time.time()
    posted = [_words(t) for t in history_store.recent_titles()]
    candidates, stale, routine, duplicate = [], 0, 0, 0
    for feed_index, feed_url in enumerate(config.RSS_FEEDS):
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
            title = html.unescape(getattr(entry, "title", "")).strip()
            if _is_routine_sebi(link, title):
                history_store.mark_news_processed(link)
                routine += 1
                continue
            ts = _published_ts(entry)
            # Entries with no readable date at all are treated as fresh.
            if ts is not None and now - ts > config.NEWS_MAX_AGE_HOURS * 3600:
                history_store.mark_news_processed(link)
                stale += 1
                continue
            words = _words(title)
            if any(_same_story(words, p) for p in posted):
                history_store.mark_news_processed(link)
                duplicate += 1
                continue
            priority = 0 if "sebi.gov.in" in link else 1
            # Feeds list newest first, so position breaks ties for undated items.
            candidates.append((priority, -(ts or now), feed_index, position, entry, words))
    if routine or stale or duplicate:
        logger.info("News Catcher: skipped %d routine SEBI filing(s), %d item(s) older than %.0fh, "
                    "%d story(ies) already posted by another outlet.",
                    routine, stale, config.NEWS_MAX_AGE_HOURS, duplicate)
    candidates.sort(key=lambda c: c[:4])

    # Rotate between outlets (each one's newest, then each one's next newest, ...)
    # so a prolific feed like ET Markets doesn't take every slot.
    seen_per_source = {}
    ranked = []
    for c in candidates:
        source = _card_meta(c[4].link)[1]
        turn = seen_per_source.get(source, 0)
        seen_per_source[source] = turn + 1
        ranked.append((c[0], turn) + c)
    ranked.sort(key=lambda r: r[:6])
    candidates = [r[2:] for r in ranked]

    # One story can sit in several feeds at once; keep only its best copy.
    picked, picked_words = [], []
    for *_, entry, words in candidates:
        if any(_same_story(words, w) for w in picked_words):
            continue
        picked.append(entry)
        picked_words.append(words)
    return picked


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
            "title": "",
            "keywords": [],
        }
    # Gemini's catchy title goes on the image; the original headline is the fallback
    # and is still what de-duplication compares against.
    display_title = content.get("title") or title
    social_caption = gemini_client.with_keywords(content["social_caption"], content.get("keywords", []))
    date = _published_date(entry)
    background = backgrounds.get_background(title or link)
    local_path = image_render.render_news_card(header, display_title, source, date, background)

    if not post_card_to_telegram(local_path, content["telegram_caption"]):
        logger.warning("Telegram post failed for %s; will retry next cycle.", link)
        return False
    history_store.mark_news_processed(link)
    history_store.add_recent_title(title)
    logger.info("News item processed and marked: %s", link)

    # Instagram/Facebook (Reel or Image Post, alternating) must never affect the
    # Telegram card post above, which has already gone out.
    if meta_configured():
        do_reel, do_post = next_meta_action("news")
        if do_reel:
            if reels_left("news") <= 0:
                logger.info("No Meta slots left today; skipping the news reel render.")
            else:
                try:
                    reel_path = reel_render.render_news_reel(header, display_title, source, date, background[0])
                    logger.info("News reel rendered at %s", reel_path)
                    post_reel_to_meta(reel_path, social_caption, kind="news")
                except Exception:
                    logger.warning("News reel render/post failed for %s.", link, exc_info=True)
        if do_post:
            try:
                post_photo_to_meta(local_path, social_caption, kind="news")
            except Exception:
                logger.warning("News photo post failed for %s.", link, exc_info=True)
    return True


def run() -> None:
    now = datetime.datetime.now(config.IST)
    if not (config.NEWS_WINDOW_START_HOUR <= now.hour < config.NEWS_WINDOW_END_HOUR):
        return
    try:
        token_monitor.check_meta_token()  # once a day; never blocks posting
    except Exception:
        logger.exception("Meta token check failed.")

    today = now.date().isoformat()

    logger.info("News Catcher: checking feeds...")
    candidates = _collect_candidates()
    if not candidates:
        logger.info("News Catcher: no new items.")
        return

    for entry in candidates[: config.MAX_NEWS_PER_RUN]:
        try:
            if _process_entry(entry):
                history_store.increment_daily_count("news_posted", today)
        except Exception:
            logger.exception("News Catcher: failed to process entry %s", getattr(entry, "link", "?"))
