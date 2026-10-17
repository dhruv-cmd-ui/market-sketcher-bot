"""Central configuration: env loading, constants, feed list."""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# Some networks advertise IPv6 but silently drop it, so every connection first
# waits out each IPv6 address. FORCE_IPV4=true makes Python resolve IPv4 only.
if os.getenv("FORCE_IPV4", "false").lower() == "true":
    import socket

    _getaddrinfo = socket.getaddrinfo

    def _ipv4_only(host, port, family=0, *args, **kwargs):
        return _getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)

    socket.getaddrinfo = _ipv4_only

BASE_DIR = Path(__file__).resolve().parent
IMAGES_DIR = BASE_DIR / "images"
IMAGES_DIR.mkdir(exist_ok=True)
HISTORY_FILE = BASE_DIR / "history.json"
LOG_FILE = BASE_DIR / "bot.log"

IST = ZoneInfo("Asia/Kolkata")

# --- Gemini ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

# --- Meta (Instagram + Facebook) ---
IG_USER_ID = os.getenv("IG_USER_ID", "")
FB_PAGE_ID = os.getenv("FB_PAGE_ID", "")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v25.0")
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# --- Branding ---
# Telegram cards point to the Telegram channel; Reels go to Instagram/Facebook.
CARD_HANDLE = os.getenv("CARD_HANDLE", "@wealthandworkflow")
REEL_HANDLE = os.getenv("REEL_HANDLE", "@marketsketchbook")

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")  # the public channel
# Your private chat with the bot, for maintenance alerts (never the public channel).
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")
# Start warning this many days before the Meta token loses access.
META_TOKEN_WARN_DAYS = int(os.getenv("META_TOKEN_WARN_DAYS", "14"))

# --- RSS feeds for the News Catcher ---
# SEBI is always posted first; the market feeds are merged newest-first.
# (Moneycontrol's RSS feeds are stale -- newest items are years old -- so they're not used.)
_default_feeds = (
    "https://www.sebi.gov.in/sebirss.xml,"
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms,"
    "https://www.livemint.com/rss/markets,"
    "https://www.business-standard.com/rss/markets-106.rss"
)
RSS_FEEDS = [
    url.strip()
    for url in os.getenv("RSS_FEEDS", _default_feeds).split(",")
    if url.strip()
]

# --- FII/DII monitor ---
# NSE's own JSON endpoint for provisional FII/DII cash-market activity
# (same one the open-source `nsepython` library uses). NSE's bot protection
# requires first loading the homepage to pick up session cookies before this
# API call will respond, rather than hitting it cold.
NSE_HOME_URL = "https://www.nseindia.com"
NSE_FII_DII_URL = os.getenv(
    "NSE_FII_DII_URL", "https://www.nseindia.com/api/fiidiiTradeReact"
)
SCRAPE_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
SCRAPE_HEADERS = {
    "User-Agent": SCRAPE_USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

# Tried in order when the primary model hits its free-tier daily quota (429).
GEMINI_FALLBACK_MODELS = [
    m.strip()
    for m in os.getenv(
        "GEMINI_FALLBACK_MODELS",
        "gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash,gemini-flash-lite-latest,"
        "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-2.5-flash-lite",
    ).split(",")
    if m.strip()
]

# Reels posted to Instagram/Facebook per IST day. Facebook allows 30 API posts per
# 24h and Instagram 100; staying under them avoids account restrictions.
MAX_REELS_PER_DAY = int(os.getenv("MAX_REELS_PER_DAY", "25"))

# Generated cards/reels in images/ older than this are deleted daily.
MEDIA_RETENTION_DAYS = int(os.getenv("MEDIA_RETENTION_DAYS", "7"))

# --- News pacing ---
# News is only posted between these IST hours (start inclusive, end exclusive).
NEWS_WINDOW_START_HOUR = int(os.getenv("NEWS_WINDOW_START_HOUR", "6"))
NEWS_WINDOW_END_HOUR = int(os.getenv("NEWS_WINDOW_END_HOUR", "23"))
# Items posted per 30-minute check, and per IST day. Feeds listed first in
# RSS_FEEDS get priority (SEBI is first by default).
MAX_NEWS_PER_RUN = int(os.getenv("MAX_NEWS_PER_RUN", "1"))
MAX_NEWS_PER_DAY = int(os.getenv("MAX_NEWS_PER_DAY", "20"))
# Items older than this are skipped (e.g. the overnight backlog at 6 AM).
NEWS_MAX_AGE_HOURS = float(os.getenv("NEWS_MAX_AGE_HOURS", "12"))
