"""YouTube Shorts publishing via the YouTube Data API v3.

Auth: a long-lived OAuth refresh token (see scripts/youtube_auth.py for the
one-time setup) is exchanged for a short-lived access token on every call --
no token is cached across runs, since each GitHub Actions run is a fresh
process anyway.

Upload: a single multipart request (snippet + status JSON part, then the
video bytes) -- our Reels are a few MB, well within what a one-shot multipart
upload handles reliably, so there's no need for the chunked resumable protocol.

A vertical video under 3 minutes is auto-detected by YouTube as a Short; no
special API flag is needed, but the description includes #Shorts to
reinforce that.
"""
import json
import os

import requests

import config

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=multipart&part=snippet,status"
_THUMBNAIL_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"


def _access_token() -> str:
    if not (config.YOUTUBE_CLIENT_ID and config.YOUTUBE_CLIENT_SECRET and config.YOUTUBE_REFRESH_TOKEN):
        raise RuntimeError("YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN not configured")
    resp = requests.post(_TOKEN_URL, data={
        "client_id": config.YOUTUBE_CLIENT_ID,
        "client_secret": config.YOUTUBE_CLIENT_SECRET,
        "refresh_token": config.YOUTUBE_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }, timeout=30)
    data = resp.json()
    if resp.status_code != 200 or "access_token" not in data:
        raise RuntimeError(f"YouTube token refresh failed ({resp.status_code}): {resp.text}")
    return data["access_token"]


_TAGS_CHAR_LIMIT = 480  # YouTube's combined-tags limit is 500; multi-word tags count +2 for quotes


def _finalize_tags(tags: list[str]) -> list[str]:
    """Channel tag always first (so it is never trimmed), dedupe, then fit the 500-char limit."""
    final, total = [], 0
    for tag in dict.fromkeys([config.YOUTUBE_CHANNEL_TAG, *tags]):
        total += len(tag) + 1 + (2 if " " in tag else 0)
        if total > _TAGS_CHAR_LIMIT:
            break
        final.append(tag)
    return final


def upload_short(local_video_path: str, title: str, description: str, tags: list[str]) -> str:
    token = _access_token()
    metadata = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": _finalize_tags(tags),
            "categoryId": config.YOUTUBE_CATEGORY_ID,
        },
        "status": {
            "privacyStatus": config.YOUTUBE_PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False,
        },
    }
    with open(local_video_path, "rb") as f:
        resp = requests.post(
            _UPLOAD_URL,
            headers={"Authorization": f"Bearer {token}"},
            files={
                "metadata": (None, json.dumps(metadata), "application/json; charset=UTF-8"),
                "video": (os.path.basename(local_video_path), f, "video/mp4"),
            },
            timeout=600,
        )
    data = resp.json()
    if resp.status_code != 200 or "id" not in data:
        raise RuntimeError(f"YouTube upload failed ({resp.status_code}): {resp.text}")
    return data["id"]


def set_thumbnail(video_id: str, local_image_path: str) -> None:
    """Best-effort: requires the channel to be phone-verified in YouTube Studio
    (Settings > Channel > Feature eligibility). Callers should catch failures."""
    token = _access_token()
    with open(local_image_path, "rb") as f:
        resp = requests.post(
            _THUMBNAIL_URL,
            params={"videoId": video_id},
            headers={"Authorization": f"Bearer {token}"},
            files={"media": (os.path.basename(local_image_path), f, "image/png")},
            timeout=120,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"YouTube thumbnail set failed ({resp.status_code}): {resp.text}")
