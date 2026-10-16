"""Checks the Meta values in .env before the bot tries to post Reels.

    .venv/Scripts/python scripts/check_meta.py      (Windows)
    .venv/bin/python scripts/check_meta.py          (VPS)
"""
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def get(path: str, **params) -> dict:
    params["access_token"] = config.META_ACCESS_TOKEN
    resp = requests.get(f"{config.GRAPH_API_BASE}/{path}", params=params, timeout=30)
    data = resp.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", data["error"]))
    return data


def check(label: str, func) -> bool:
    try:
        print(f"OK    {label}: {func()}")
        return True
    except Exception as exc:
        print(f"FAIL  {label}: {exc}")
        return False


if __name__ == "__main__":
    missing = [k for k in ("META_ACCESS_TOKEN", "FB_PAGE_ID", "IG_USER_ID") if not getattr(config, k)]
    if missing:
        sys.exit(f"Missing in .env: {', '.join(missing)}")

    results = [
        check("Token belongs to", lambda: get("me", fields="id,name")),
        check("Facebook Page", lambda: get(config.FB_PAGE_ID, fields="id,name")),
        check("Page's linked Instagram", lambda: get(config.FB_PAGE_ID, fields="instagram_business_account")
              .get("instagram_business_account", "NOT LINKED - link Instagram to the Page")),
        check("Instagram account", lambda: get(config.IG_USER_ID, fields="id,username")),
        check("Instagram posts used in last 24h", lambda: get(f"{config.IG_USER_ID}/content_publishing_limit",
                                                            fields="quota_usage,config")),
    ]
    print("\nAll good - Reels will post to Instagram and Facebook." if all(results)
          else "\nFix the FAIL lines above (see deploy/DEPLOY.md, part 2).")
