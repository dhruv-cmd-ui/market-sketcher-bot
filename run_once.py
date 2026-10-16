"""Single-run entrypoint for cron-style hosts (GitHub Actions).

    python run_once.py news      # one News Catcher check (posts only 06:00-23:00 IST)
    python run_once.py fii       # one FII/DII check (posts only 17:00-21:00 IST, Mon-Fri)
    python run_once.py selftest  # checks every external service is reachable; posts nothing

main.py is the always-on alternative that runs the same tasks on an internal schedule.
"""
import argparse
import logging
import sys

import requests

import config
import feeds


def _selftest() -> bool:
    from google import genai
    from google.genai import types
    from tasks.fii_dii_monitor import _extract_values, _fetch_fii_dii_records

    def tg():
        me = requests.get(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getMe", timeout=20).json()
        if not me.get("ok"):
            raise RuntimeError(me)
        return "@" + me["result"]["username"]

    def rss():
        counts = {url.split("/")[2]: len(feeds.fetch(url).entries) for url in config.RSS_FEEDS}
        if not all(counts.values()):
            raise RuntimeError(f"empty feed(s): {counts}")
        return counts

    def nse():
        report_date, values = _extract_values(_fetch_fii_dii_records())
        return f"{report_date}: FII net {values['fii']['net']}, DII net {values['dii']['net']}"

    def gemini():
        client = genai.Client(api_key=config.GEMINI_API_KEY, http_options=types.HttpOptions(timeout=30_000))
        return f"key accepted, {client.models.get(model=config.GEMINI_MODEL).name} available"

    ok = True
    for name, check in (("Telegram", tg), ("RSS feeds", rss), ("NSE FII/DII", nse), ("Gemini", gemini)):
        try:
            print(f"OK    {name}: {check()}")
        except Exception as exc:
            ok = False
            print(f"FAIL  {name}: {type(exc).__name__}: {exc}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task", choices=["news", "fii", "selftest"])
    task = parser.parse_args().task
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    for noisy in ("httpx", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if task == "selftest":
        return 0 if _selftest() else 1
    if task == "news":
        from tasks import news_catcher
        news_catcher.run()
    else:
        from tasks import fii_dii_monitor
        fii_dii_monitor.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
