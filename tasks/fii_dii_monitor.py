"""Task 2: Smart FII/DII Data Monitor.

Polls NSE's own provisional FII/DII cash-market JSON endpoint every 15
minutes between 17:00-21:00 IST on weekdays. The first time the report's own
date matches today it posts a still card to Telegram and an animated Reel to
Instagram + Facebook.

NOTE: `https://www.nseindia.com/api/fiidiiTradeReact` is an unofficial-but-
widely-used internal NSE endpoint (the same one the open-source `nsepython`
library relies on) and its shape could change without notice. NSE's bot
protection also requires loading the homepage first to pick up session
cookies -- a cold request straight to the API endpoint will hang or be
blocked. If NSE changes the response shape, parsing below raises and this
module logs + skips until it's fixed.
"""
import datetime
import logging

import requests

import config
import gemini_client
import history_store
import image_render
import reel_render
from multi_publish import post_card_to_telegram, post_reel_to_meta

logger = logging.getLogger(__name__)

_DATE_FORMATS = ["%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y"]


def _in_scrape_window(now_ist: datetime.datetime) -> bool:
    if now_ist.weekday() > 4:  # Mon=0 ... Sun=6
        return False
    start = now_ist.replace(hour=17, minute=0, second=0, microsecond=0)
    end = now_ist.replace(hour=21, minute=0, second=0, microsecond=0)
    return start <= now_ist <= end


def _parse_date(raw: str) -> datetime.date:
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format from NSE: {raw!r}")


def _fetch_fii_dii_records() -> list[dict]:
    session = requests.Session()
    session.headers.update(config.SCRAPE_HEADERS)
    # Priming request: NSE's bot protection issues cookies here that the
    # API call below requires; skipping this makes the API request hang/403.
    session.get(config.NSE_HOME_URL, timeout=15)
    resp = session.get(config.NSE_FII_DII_URL, timeout=15)
    resp.raise_for_status()
    records = resp.json()
    if not isinstance(records, list) or not records:
        raise ValueError(f"Unexpected NSE FII/DII response shape: {records!r}")
    return records


def _extract_values(records: list[dict]) -> tuple[datetime.date, dict]:
    values = {}
    report_date = None
    for record in records:
        category = str(record.get("category", "")).upper()
        buy = float(record["buyValue"])
        sell = float(record["sellValue"])
        net = float(record["netValue"])
        record_date = _parse_date(str(record["date"]))
        report_date = report_date or record_date

        if "FII" in category and "fii" not in values:
            values["fii"] = {"buy": buy, "sell": sell, "net": net}
        elif "DII" in category and "dii" not in values:
            values["dii"] = {"buy": buy, "sell": sell, "net": net}

    if "fii" not in values or "dii" not in values or report_date is None:
        raise ValueError(f"Could not locate both FII and DII records; got: {records!r}")
    return report_date, values


def _build_context(report_date: datetime.date, values: dict) -> str:
    fii, dii = values["fii"], values["dii"]
    return (
        f"Date: {report_date.isoformat()}\n"
        f"FII (Foreign Institutional Investors) - Buy: {fii['buy']} Cr, "
        f"Sell: {fii['sell']} Cr, Net: {fii['net']} Cr\n"
        f"DII (Domestic Institutional Investors) - Buy: {dii['buy']} Cr, "
        f"Sell: {dii['sell']} Cr, Net: {dii['net']} Cr"
    )


def run() -> None:
    now_ist = datetime.datetime.now(config.IST)
    if not _in_scrape_window(now_ist):
        return

    today_str = now_ist.date().isoformat()
    if history_store.already_posted_fii_dii_today(today_str):
        return

    try:
        records = _fetch_fii_dii_records()
        report_date, values = _extract_values(records)
    except Exception:
        logger.warning("FII/DII Monitor: NSE fetch/parse failed this cycle; will retry.", exc_info=True)
        return

    if report_date.isoformat() != today_str:
        logger.info("FII/DII Monitor: latest NSE report (%s) isn't today's yet.", report_date)
        return

    try:
        context = _build_context(report_date, values)
        try:
            content = gemini_client.generate_content(context)
        except Exception:
            logger.warning("Gemini captions unavailable; using template captions.", exc_info=True)
            fii, dii = values["fii"]["net"], values["dii"]["net"]
            summary = (f"FII net {'bought' if fii >= 0 else 'sold'} ₹{abs(fii):,.2f} Cr, "
                       f"DII net {'bought' if dii >= 0 else 'sold'} ₹{abs(dii):,.2f} Cr "
                       f"in the cash market on {report_date.strftime('%d %b %Y')} (provisional, NSE).")
            content = {
                "telegram_caption": f"FII / DII Activity\n\n{summary}",
                "social_caption": f"{summary}\n\n#FII #DII #StockMarket #Nifty #Sensex",
            }
        local_path = image_render.render_fii_dii_card(report_date, values)

        telegram_ok = post_card_to_telegram(local_path, content["telegram_caption"])

        if telegram_ok:
            history_store.mark_fii_dii_posted(today_str)
            logger.info("FII/DII Monitor: posted and marked for %s.", today_str)
        else:
            logger.warning("FII/DII Monitor: Telegram post failed; will retry next cycle.")
            return
    except Exception:
        logger.exception("FII/DII Monitor: failed to generate/publish content.")
        return

    # The Reel (Instagram + Facebook only) must never affect the Telegram card post.
    try:
        reel_path = reel_render.render_fii_dii_reel(report_date, values)
        logger.info("FII/DII Monitor: reel rendered at %s", reel_path)
        post_reel_to_meta(reel_path, gemini_client.with_keywords(content["social_caption"],
                                                                 content.get("keywords", [])))
    except Exception:
        logger.warning("FII/DII Monitor: reel render/post failed.", exc_info=True)
