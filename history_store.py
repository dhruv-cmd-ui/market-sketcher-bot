"""Atomic JSON-backed history: processed news URLs, FII/DII post date, daily post counters."""
import json
import logging
import os
import threading

import config

logger = logging.getLogger(__name__)

_lock = threading.Lock()

_DEFAULT = {"processed_news_urls": [], "last_fii_dii_post_date": None}


def load() -> dict:
    if not config.HISTORY_FILE.exists():
        return dict(_DEFAULT)
    try:
        with open(config.HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key, default_value in _DEFAULT.items():
            data.setdefault(key, default_value)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read history.json (%s); starting fresh.", exc)
        return dict(_DEFAULT)


def save(data: dict) -> None:
    tmp_path = f"{config.HISTORY_FILE}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, config.HISTORY_FILE)


def is_news_processed(url: str) -> bool:
    with _lock:
        return url in load().get("processed_news_urls", [])


def mark_news_processed(url: str) -> None:
    with _lock:
        data = load()
        urls = data.setdefault("processed_news_urls", [])
        if url not in urls:
            urls.append(url)
            # Keep the history file from growing unbounded over months of polling.
            data["processed_news_urls"] = urls[-500:]
            save(data)


def daily_count(key: str, date_str: str) -> int:
    """Per-IST-day counter (e.g. "reels_posted", "news_posted"); resets when the date changes."""
    with _lock:
        counter = load().get(key) or {}
        return counter.get("count", 0) if counter.get("date") == date_str else 0


def increment_daily_count(key: str, date_str: str) -> None:
    with _lock:
        data = load()
        counter = data.get(key) or {}
        count = counter.get("count", 0) if counter.get("date") == date_str else 0
        data[key] = {"date": date_str, "count": count + 1}
        save(data)


def already_posted_fii_dii_today(date_str: str) -> bool:
    with _lock:
        return load().get("last_fii_dii_post_date") == date_str


def mark_fii_dii_posted(date_str: str) -> None:
    with _lock:
        data = load()
        data["last_fii_dii_post_date"] = date_str
        save(data)
