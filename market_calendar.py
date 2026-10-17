"""NSE trading-day calendar: weekends plus NSE's cash-market trading holidays.

Zero-maintenance: no dates are stored in the code. Sources, in order:
  1. NSE's own holiday API
  2. Upstox's public market-holidays API (no key needed), if NSE is unreachable
  3. the last list either source returned, cached in history.json, if both are down
  4. the `holidays` package's computed NSE calendar, which works offline for any
     year (it can't know one-off holidays such as an election day)
A successful online fetch is cached and refreshed weekly.
"""
import datetime
import logging

import holidays
import requests

import config
import history_store

logger = logging.getLogger(__name__)

_NSE_API = "https://www.nseindia.com/api/holiday-master"
_UPSTOX_API = "https://api.upstox.com/v2/market/holidays"
_REFRESH_DAYS = 7


def _from_nse(year: int) -> list[str]:
    session = requests.Session()
    session.headers.update(config.SCRAPE_HEADERS)
    try:
        session.get(config.NSE_HOME_URL, timeout=15)  # cookie priming; NSE sometimes answers 403 here
    except requests.RequestException:
        pass
    resp = session.get(_NSE_API, params={"type": "trading"}, timeout=20)
    resp.raise_for_status()
    dates = [datetime.datetime.strptime(h["tradingDate"], "%d-%b-%Y").date()
             for h in resp.json().get("CM", [])]
    return [d.isoformat() for d in dates if d.year == year]


def _from_upstox(year: int) -> list[str]:
    resp = requests.get(_UPSTOX_API, headers={"Accept": "application/json"}, timeout=20)
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != "success":
        raise ValueError(f"Upstox holidays API returned {body.get('status')!r}")
    return [h["date"] for h in body.get("data", [])
            if h.get("holiday_type") == "TRADING_HOLIDAY" and "NSE" in (h.get("closed_exchanges") or [])
            and h.get("date", "").startswith(str(year))]


def _computed(year: int) -> list[str]:
    return [d.isoformat() for d in holidays.financial_holidays("XNSE", years=year)]


def _holidays(today: datetime.date) -> set[str]:
    cached = history_store.get_value("nse_holidays") or {}
    same_year = cached.get("year") == today.year and cached.get("dates")
    if same_year and cached.get("fetched_on") and \
            (today - datetime.date.fromisoformat(cached["fetched_on"])).days < _REFRESH_DAYS:
        return set(cached["dates"])

    for name, fetch in (("NSE", _from_nse), ("Upstox", _from_upstox)):
        try:
            dates = fetch(today.year)
            if not dates:
                raise ValueError("empty holiday list")
            history_store.set_value("nse_holidays", {"year": today.year, "fetched_on": today.isoformat(),
                                                      "source": name, "dates": dates})
            logger.info("NSE holiday list refreshed from %s: %d holidays in %d.", name, len(dates), today.year)
            return set(dates)
        except Exception as exc:
            logger.warning("Holiday source %s unavailable: %s", name, exc)

    if same_year:
        logger.warning("Using the cached NSE holiday list from %s (%s).", cached.get("fetched_on"), cached.get("source"))
        return set(cached["dates"])
    logger.warning("Using the computed NSE holiday calendar for %d (may miss one-off holidays).", today.year)
    return set(_computed(today.year))


def is_trading_day(day: datetime.date | None = None) -> bool:
    day = day or datetime.datetime.now(config.IST).date()
    if day.weekday() >= 5:
        return False
    return day.isoformat() not in _holidays(day)
