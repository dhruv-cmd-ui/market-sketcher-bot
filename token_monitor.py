"""Daily check that the Meta token will keep working; warns the admin privately on Telegram.

A Page token can say "never expires" and still stop working when Meta's data-access
window (about 90 days from when it was generated) closes, so that date is what's checked.
"""
import datetime
import logging

import requests

import config
import history_store
from publishers import telegram

logger = logging.getLogger(__name__)

REFRESH_STEPS = (
    "How to refresh (about 5 minutes):\n"
    "1. Graph API Explorer (developers.facebook.com/tools/explorer), app Market Sketchbook Bot, "
    "Configurations tab, select 'Bot posting', Generate Access Token.\n"
    "2. Extend it in the Access Token Debugger.\n"
    f"3. Run {config.FB_PAGE_ID or '<FB_PAGE_ID>'}?fields=name,access_token and copy the access_token.\n"
    "4. Put it in GitHub: Settings > Secrets and variables > Actions > META_ACCESS_TOKEN (and in .env)."
)


def _expiry(token: str) -> tuple[bool, datetime.datetime | None, str]:
    resp = requests.get(f"{config.GRAPH_API_BASE}/debug_token",
                        params={"input_token": token, "access_token": token}, timeout=30).json()
    if "error" in resp:
        return False, None, resp["error"].get("message", "unknown error")
    data = resp.get("data", {})
    if not data.get("is_valid"):
        return False, None, (data.get("error") or {}).get("message", "token is not valid")
    stamps = [t for t in (data.get("expires_at"), data.get("data_access_expires_at")) if t]
    return True, (datetime.datetime.fromtimestamp(min(stamps), config.IST) if stamps else None), ""


def check_meta_token() -> None:
    if not config.META_ACCESS_TOKEN:
        return
    today = datetime.datetime.now(config.IST).date().isoformat()
    if history_store.get_value("meta_token_checked_on") == today:
        return

    valid, ends, error = _expiry(config.META_ACCESS_TOKEN)
    if not valid:
        message = (f"Market Sketchbook bot: the Meta token has stopped working ({error}). "
                   f"Reels to Instagram and Facebook are paused; Telegram is unaffected.\n\n{REFRESH_STEPS}")
    else:
        days_left = (ends - datetime.datetime.now(config.IST)).days if ends else None
        logger.info("Meta token: %s", f"{days_left} day(s) of access left (until {ends:%d %b %Y})"
                    if ends else "no expiry")
        if days_left is None or days_left > config.META_TOKEN_WARN_DAYS:
            history_store.set_value("meta_token_checked_on", today)
            return
        message = (f"Market Sketchbook bot: the Meta token loses access on {ends:%d %b %Y} "
                   f"({max(days_left, 0)} day(s) left). After that, Reels to Instagram and Facebook "
                   f"will stop.\n\n{REFRESH_STEPS}")

    if not config.ADMIN_CHAT_ID:
        logger.warning("Meta token needs attention but ADMIN_CHAT_ID isn't set: %s", message)
    else:
        try:
            telegram.send_text(config.ADMIN_CHAT_ID, message)
            logger.info("Sent Meta token reminder to the admin.")
        except Exception:
            logger.exception("Could not send Meta token reminder.")
            return  # retry on the next run
    history_store.set_value("meta_token_checked_on", today)
