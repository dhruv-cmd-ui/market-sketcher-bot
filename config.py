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

# --- YouTube (FII/DII Shorts) ---
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
YOUTUBE_PRIVACY_STATUS = os.getenv("YOUTUBE_PRIVACY_STATUS", "public")
YOUTUBE_CATEGORY_ID = os.getenv("YOUTUBE_CATEGORY_ID", "25")  # News & Politics
YOUTUBE_CHANNEL_TAG = os.getenv("YOUTUBE_CHANNEL_TAG", "Market Sketch Book")  # added to every Short

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

# Reels/Posts to Instagram/Facebook per IST day -- a generous safety ceiling, not the
# day-to-day target (that's the fixed windows below). Facebook allows 30 API posts
# per 24h and Instagram 100. On NSE trading days one slot is held back for the
# FII/DII Reel until it posts or its window closes.
MAX_REELS_PER_DAY = int(os.getenv("MAX_REELS_PER_DAY", "25"))

# News Reels/Post to Instagram+Facebook, at most once each in these fixed daily
# windows (IST hours): a Reel in the morning, a Reel in the evening, a single
# Image Post around midday. Outside these windows, news still posts to Telegram
# as usual but nothing goes to Meta.
NEWS_MORNING_REEL_START_HOUR = int(os.getenv("NEWS_MORNING_REEL_START_HOUR", "6"))
NEWS_MORNING_REEL_END_HOUR = int(os.getenv("NEWS_MORNING_REEL_END_HOUR", "9"))
# PAUSED: Instagram/Facebook currently get only the FII/DII Reel plus one morning
# news Image Post (by 9 AM). Set META_FULL_SCHEDULE=true to restore the original
# morning Reel (8-10), midday Post and evening Reel.
META_FULL_SCHEDULE = os.getenv("META_FULL_SCHEDULE", "false").lower() == "true"
NEWS_AFTERNOON_POST_START_HOUR = int(os.getenv("NEWS_AFTERNOON_POST_START_HOUR", "12"))
NEWS_AFTERNOON_POST_END_HOUR = int(os.getenv("NEWS_AFTERNOON_POST_END_HOUR", "14"))
NEWS_EVENING_REEL_START_HOUR = int(os.getenv("NEWS_EVENING_REEL_START_HOUR", "18"))
NEWS_EVENING_REEL_END_HOUR = int(os.getenv("NEWS_EVENING_REEL_END_HOUR", "20"))

# FII/DII polling window (IST hours, weekdays). NSE's provisional report
# sometimes lands well after 9 PM, so this stays open late to not miss it.
FII_WINDOW_START_HOUR = int(os.getenv("FII_WINDOW_START_HOUR", "17"))
FII_WINDOW_END_HOUR = int(os.getenv("FII_WINDOW_END_HOUR", "23"))

# Generated cards/reels in images/ older than this are deleted daily.
MEDIA_RETENTION_DAYS = int(os.getenv("MEDIA_RETENTION_DAYS", "7"))

# --- News pacing ---
# News is only posted between these IST hours (start inclusive, end exclusive).
NEWS_WINDOW_START_HOUR = int(os.getenv("NEWS_WINDOW_START_HOUR", "6"))
NEWS_WINDOW_END_HOUR = int(os.getenv("NEWS_WINDOW_END_HOUR", "23"))
# Items posted per 30-minute check. Telegram has no daily cap; Reels are limited
# by MAX_REELS_PER_DAY instead.
MAX_NEWS_PER_RUN = int(os.getenv("MAX_NEWS_PER_RUN", "1"))
# Items older than this are skipped (e.g. the overnight backlog at 6 AM).
NEWS_MAX_AGE_HOURS = float(os.getenv("NEWS_MAX_AGE_HOURS", "12"))
