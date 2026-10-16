"""RSS fetching with a hard timeout (feedparser.parse(url) has none and can hang a run)."""
import feedparser
import requests

import config

FEED_TIMEOUT_SECONDS = 90  # ET Markets regularly takes ~60s to respond


def fetch(url: str):
    resp = requests.get(url, headers={"User-Agent": config.SCRAPE_USER_AGENT}, timeout=FEED_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return feedparser.parse(resp.content)
