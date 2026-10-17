"""NSE trading-day calendar: weekends plus NSE's cash-market trading holidays.

The holiday list comes from NSE's own holiday API, refreshed weekly and cached in
history.json. If NSE can't be reached it falls back to the cache, then to the
built-in list below (update it each December from NSE's published calendar).
"""
import datetime
import logging

import requests

import config
import history_store

logger = logging.getLogger(__name__)

_HOLIDAY_API = "https://www.nseindia.com/api/holiday-master"
_REFRESH_DAYS = 7

# NSE cash-market (CM) trading holidays, as published by NSE.
_BUILT_IN = {
    2026: ["2026-01-15", "2026-01-26", "2026-02-15", "2026-03-03", "2026-03-21", "2026-03-26",
           "2026-03-31", "2026-04-03", "2026-04-14", "2026-05-01", "2026-05-28", "2026-06-26",
           "2026-08-15", "2026-09-14", "2026-10-02", "2026-10-20", "2026-11-08", "2026-11-10",
           "2026-11-24", "2026-12-25"],
}


def _fetch_from_nse() -> list[str]:
    session = requests.Session()
    session.headers.update(config.SCRAPE_HEADERS)
    try:
        session.get(config.NSE_HOME_URL, timeout=15)  # cookie priming; NSE sometimes answers 403 here
    except requests.RequestException:
        pass
    resp = session.get(_HOLIDAY_API, params={"type": "trading"}, timeout=20)
    resp.raise_for_status()
    dates = [datetime.datetime.strptime(h["tradingDate"], "%d-%b-%Y").date().isoformat()
             for h in resp.json().get("CM", [])]
    if not dates:
        raise ValueError("NSE holiday list came back empty")
    return dates


def _holidays(today: datetime.date) -> set[str]:
    cached = history_store.get_value("nse_holidays") or {}
    fetched_on = cached.get("fetched_on")
    fresh = (fetched_on and cached.get("year") == today.year and
             (today - datetime.date.fromisoformat(fetched_on)).days < _REFRESH_DAYS)
    if not fresh:
        try:
            dates = _fetch_from_nse()
            cached = {"year": today.year, "fetched_on": today.isoformat(), "dates": dates}
            history_store.set_value("nse_holidays", cached)
            logger.info("Refreshed NSE holiday list: %d holidays.", len(dates))
        except Exception:
            logger.warning("Could not refresh NSE holidays; using cached/built-in list.", exc_info=True)
    dates = set(cached.get("dates", [])) if cached.get("year") == today.year else set()
    if not dates:
        dates = set(_BUILT_IN.get(today.year, []))
        if not dates:
            logger.warning("No NSE holiday list for %d; only weekends are treated as closed.", today.year)
    return dates


def is_trading_day(day: datetime.date | None = None) -> bool:
    day = day or datetime.datetime.now(config.IST).date()
    if day.weekday() >= 5:
        return False
    return day.isoformat() not in _holidays(day)
