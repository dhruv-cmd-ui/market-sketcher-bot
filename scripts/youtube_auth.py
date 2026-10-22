"""One-time setup: turns a Google OAuth Client ID/Secret into a YOUTUBE_REFRESH_TOKEN.

Uses the OAuth 2.0 Device Authorization flow -- no local server or redirect
URI needed. You'll visit a URL, enter a short code, and approve once; this
script then prints the refresh token to save into .env and GitHub Secrets.

    .venv\\Scripts\\python scripts\\youtube_auth.py
"""
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

DEVICE_URL = "https://oauth2.googleapis.com/device/code"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"


def main() -> None:
    client_id = config.YOUTUBE_CLIENT_ID or input("YOUTUBE_CLIENT_ID (from Google Cloud Console): ").strip()
    client_secret = config.YOUTUBE_CLIENT_SECRET or input("YOUTUBE_CLIENT_SECRET: ").strip()

    device = requests.post(DEVICE_URL, data={"client_id": client_id, "scope": SCOPE}, timeout=30).json()
    if "device_code" not in device:
        sys.exit(f"Could not start device authorization: {device}")

    print(f"\n1. Open: {device['verification_url']}")
    print(f"2. Enter this code: {device['user_code']}")
    print("3. Sign in with the Google account for your YouTube channel and approve.\n")
    print("Waiting for approval...")

    interval = device.get("interval", 5)
    deadline = time.time() + device.get("expires_in", 1800)
    while time.time() < deadline:
        time.sleep(interval)
        token = requests.post(TOKEN_URL, data={
            "client_id": client_id, "client_secret": client_secret,
            "device_code": device["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }, timeout=30).json()
        if "refresh_token" in token:
            print("\nApproved. Add these to .env and to your GitHub repo's Actions secrets:\n")
            print(f"YOUTUBE_CLIENT_ID={client_id}")
            print(f"YOUTUBE_CLIENT_SECRET={client_secret}")
            print(f"YOUTUBE_REFRESH_TOKEN={token['refresh_token']}")
            return
        if token.get("error") not in ("authorization_pending", "slow_down"):
            sys.exit(f"Authorization failed: {token}")

    sys.exit("Timed out waiting for approval; run this again.")


if __name__ == "__main__":
    main()
