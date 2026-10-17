"""Telegram Bot API publishing (sendPhoto)."""
import requests

import config

_API_BASE = "https://api.telegram.org"


def post(local_image_path: str, caption: str) -> None:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not configured")

    url = f"{_API_BASE}/bot{config.TELEGRAM_BOT_TOKEN}/sendPhoto"
    with open(local_image_path, "rb") as photo_file:
        resp = requests.post(
            url,
            data={"chat_id": config.TELEGRAM_CHAT_ID, "caption": caption},
            files={"photo": photo_file},
            timeout=60,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Telegram sendPhoto failed ({resp.status_code}): {resp.text}")


def send_text(chat_id: str, text: str) -> None:
    resp = requests.post(f"{_API_BASE}/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
                         data={"chat_id": chat_id, "text": text}, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Telegram sendMessage failed ({resp.status_code}): {resp.text}")

