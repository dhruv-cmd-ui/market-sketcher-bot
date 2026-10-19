"""Instagram + Facebook Page photo (Image Post) publishing.

Facebook's /photos endpoint accepts a direct binary upload, same as Reels.
Instagram's photo API has no binary-upload path -- it only accepts a public
image_url that Meta's servers fetch themselves -- so Instagram photo posts go
through image_host.publish_public_copy() first.
"""
import requests

import config


def post_facebook_photo(local_image_path: str, caption: str) -> str:
    if not config.FB_PAGE_ID or not config.META_ACCESS_TOKEN:
        raise RuntimeError("FB_PAGE_ID / META_ACCESS_TOKEN not configured")
    with open(local_image_path, "rb") as f:
        resp = requests.post(
            f"{config.GRAPH_API_BASE}/{config.FB_PAGE_ID}/photos",
            data={"caption": caption, "access_token": config.META_ACCESS_TOKEN},
            files={"source": f},
            timeout=120,
        )
    data = resp.json()
    if resp.status_code != 200 or "id" not in data:
        raise RuntimeError(f"Facebook photo post failed ({resp.status_code}): {resp.text}")
    return data["id"]


def post_instagram_photo(image_public_url: str, caption: str) -> str:
    if not config.IG_USER_ID or not config.META_ACCESS_TOKEN:
        raise RuntimeError("IG_USER_ID / META_ACCESS_TOKEN not configured")

    container = requests.post(
        f"{config.GRAPH_API_BASE}/{config.IG_USER_ID}/media",
        data={"image_url": image_public_url, "caption": caption, "access_token": config.META_ACCESS_TOKEN},
        timeout=60,
    ).json()
    if "id" not in container:
        raise RuntimeError(f"Instagram photo container failed: {container}")

    publish = requests.post(
        f"{config.GRAPH_API_BASE}/{config.IG_USER_ID}/media_publish",
        data={"creation_id": container["id"], "access_token": config.META_ACCESS_TOKEN},
        timeout=60,
    ).json()
    if "id" not in publish:
        raise RuntimeError(f"Instagram photo publish failed: {publish}")
    return publish["id"]
