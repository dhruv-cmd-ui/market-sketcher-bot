"""Instagram + Facebook Page Reels via direct binary upload to rupload.facebook.com.

Unlike photo posts, Reels don't need the file on a public server: both APIs
accept the local MP4 bytes.
"""
import os
import time

import requests

import config

_IG_STATUS_POLLS = 20
_IG_STATUS_DELAY_SECONDS = 15


def _raise_for(resp: requests.Response, what: str) -> dict:
    if resp.status_code != 200:
        raise RuntimeError(f"{what} failed ({resp.status_code}): {resp.text}")
    return resp.json()


def _upload_binary(url: str, path: str) -> None:
    with open(path, "rb") as f:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"OAuth {config.META_ACCESS_TOKEN}",
                "offset": "0",
                "file_size": str(os.path.getsize(path)),
                "Content-Type": "application/octet-stream",
            },
            data=f,
            timeout=600,
        )
    _raise_for(resp, "Reel binary upload")


def post_instagram_reel(local_video_path: str, caption: str) -> str:
    if not config.IG_USER_ID or not config.META_ACCESS_TOKEN:
        raise RuntimeError("IG_USER_ID / META_ACCESS_TOKEN not configured")

    container = _raise_for(requests.post(
        f"{config.GRAPH_API_BASE}/{config.IG_USER_ID}/media",
        data={"media_type": "REELS", "upload_type": "resumable", "caption": caption,
              "share_to_feed": "true", "access_token": config.META_ACCESS_TOKEN},
        timeout=60,
    ), "Instagram reel container")["id"]

    _upload_binary(f"https://rupload.facebook.com/ig-api-upload/{config.GRAPH_API_VERSION}/{container}",
                   local_video_path)

    for _ in range(_IG_STATUS_POLLS):
        status = _raise_for(requests.get(
            f"{config.GRAPH_API_BASE}/{container}",
            params={"fields": "status_code,status", "access_token": config.META_ACCESS_TOKEN},
            timeout=30,
        ), "Instagram reel status")
        code = status.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram reel processing {code}: {status}")
        time.sleep(_IG_STATUS_DELAY_SECONDS)
    else:
        raise RuntimeError("Instagram reel did not finish processing in time")

    return _raise_for(requests.post(
        f"{config.GRAPH_API_BASE}/{config.IG_USER_ID}/media_publish",
        data={"creation_id": container, "access_token": config.META_ACCESS_TOKEN},
        timeout=60,
    ), "Instagram reel publish")["id"]


def post_facebook_reel(local_video_path: str, caption: str) -> str:
    if not config.FB_PAGE_ID or not config.META_ACCESS_TOKEN:
        raise RuntimeError("FB_PAGE_ID / META_ACCESS_TOKEN not configured")

    endpoint = f"{config.GRAPH_API_BASE}/{config.FB_PAGE_ID}/video_reels"
    start = _raise_for(requests.post(
        endpoint, data={"upload_phase": "start", "access_token": config.META_ACCESS_TOKEN}, timeout=60,
    ), "Facebook reel start")
    video_id = start["video_id"]
    upload_url = start.get("upload_url") or \
        f"https://rupload.facebook.com/video-upload/{config.GRAPH_API_VERSION}/{video_id}"

    _upload_binary(upload_url, local_video_path)

    _raise_for(requests.post(endpoint, data={
        "upload_phase": "finish", "video_id": video_id, "video_state": "PUBLISHED",
        "description": caption, "access_token": config.META_ACCESS_TOKEN,
    }, timeout=60), "Facebook reel publish")
    return video_id
