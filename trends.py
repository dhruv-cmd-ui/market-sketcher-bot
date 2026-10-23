"""Trending-news signals for the News Catcher, so higher-interest stories are
prioritized over just-published-first ones.

Two free, no-key sources:
  1. NSE's own "most active securities by volume" list -- first-party, reliable,
     stock-market-specific. Used as the primary signal (see is_trending_headline).
  2. Google Trends per-topic search interest, via the unofficial `pytrends`
     library -- used only as a light tie-break among the top few candidates,
     since it's a reverse-engineered scraper that can break or rate-limit at
     any time (Google's own "daily trending searches" endpoint pytrends used to
     use is already gone as of 2026; only interest_over_time still works).
Both fail soft: if either is unavailable, selection just falls back to the
existing recency/source-rotation ranking, exactly like every other optional
signal in this project (NSE holidays, Gemini fallbacks, etc.).
"""
import logging
import re
import time

import requests

import config
import history_store

logger = logging.getLogger(__name__)

_NSE_MOST_ACTIVE_URL = "https://www.nseindia.com/api/live-analysis-most-active-securities?index=volume"
_NSE_CACHE_SECONDS = 20 * 60  # the list moves through the trading day; refresh every 20 min

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _fetch_nse_most_active() -> set[str]:
    session = requests.Session()
    session.headers.update(config.SCRAPE_HEADERS)
    session.get(config.NSE_HOME_URL, timeout=15)  # cookie priming, same as the FII/DII endpoint
    resp = session.get(_NSE_MOST_ACTIVE_URL, timeout=15)
    resp.raise_for_status()
    rows = resp.json().get("data", [])
    symbols = {str(r["symbol"]).lower() for r in rows if r.get("symbol")}
    if not symbols:
        raise ValueError("NSE most-active response had no symbols")
    return symbols


def nse_most_active_symbols() -> set[str]:
    cached = history_store.get_value("nse_most_active") or {}
    if time.time() - cached.get("fetched_at", 0) < _NSE_CACHE_SECONDS:
        return set(cached.get("symbols", []))
    try:
        symbols = _fetch_nse_most_active()
        history_store.set_value("nse_most_active", {"fetched_at": time.time(), "symbols": sorted(symbols)})
        return symbols
    except Exception:
        logger.warning("Could not refresh NSE most-active list; using the stale/empty cache.", exc_info=True)
        return set(cached.get("symbols", []))


def is_trending_headline(title: str, symbols: set[str]) -> bool:
    """True if a currently most-active NSE symbol appears in the headline, either as
    its own word (e.g. "Suzlon") or as two adjacent words run together (e.g. "Yes Bank" -> "yesbank")."""
    if not symbols:
        return False
    words = _TOKEN_RE.findall(title.lower())
    if any(w in symbols for w in words):
        return True
    return any(words[i] + words[i + 1] in symbols for i in range(len(words) - 1))


_TRENDS_MAX_CANDIDATES = 3
_TRENDS_CALL_DELAY_SECONDS = 1.5
# A full headline is too specific for Google Trends to have data on; the leading
# capitalized phrase is usually the subject (company/index name), which gets
# real search-volume data far more often, e.g. "Zetwerk shares debut at..." -> "Zetwerk".
_SUBJECT_RE = re.compile(r"^([A-Z][a-zA-Z&]{1,}(?:\s+[A-Z][a-zA-Z&]{1,}){0,2})")


def _extract_subject(title: str) -> str:
    match = _SUBJECT_RE.match(title)
    subject = match.group(1) if match else ""
    return subject if len(subject) >= 3 else " ".join(title.split()[:3])


def _google_interest(query: str) -> float | None:
    from pytrends.request import TrendReq
    pytrends = TrendReq(hl="en-IN", tz=330)
    pytrends.build_payload([query], timeframe="now 4-H", geo="IN")
    df = pytrends.interest_over_time()
    if df.empty or query not in df.columns:
        return None
    return float(df[query].tail(6).mean())  # recent average, not just the latest (possibly partial) point


def rerank_by_search_interest(entries: list) -> list:
    """Re-sorts the first _TRENDS_MAX_CANDIDATES of `entries` (objects with a
    `.title`) by current Google Trends search interest, most-searched first.
    Leaves the rest of the list untouched. Returns `entries` unchanged if Google
    Trends is unavailable this run (fails on the first call) -- never raises."""
    if len(entries) < 2:
        return entries
    head, tail = entries[:_TRENDS_MAX_CANDIDATES], entries[_TRENDS_MAX_CANDIDATES:]
    scored = []
    for i, entry in enumerate(head):
        query = _extract_subject(entry.title)
        try:
            score = _google_interest(query)
        except Exception as exc:
            if i == 0:
                logger.info("Google Trends unavailable this run (%s); keeping recency order.", exc)
                return entries
            logger.info("Google Trends lookup failed for %r: %s", query, exc)
            score = None
        scored.append((score if score is not None else -1, entry))
        time.sleep(_TRENDS_CALL_DELAY_SECONDS)
    scored.sort(key=lambda s: s[0], reverse=True)
    logger.info("Search-interest ranking: %s", [(round(s, 1), e.title[:50]) for s, e in scored])
    return [e for _, e in scored] + tail
