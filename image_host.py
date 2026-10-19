"""Free, zero-maintenance public hosting for Instagram photo posts.

Instagram's photo-publishing API requires a publicly reachable image_url --
there is no binary-upload path for photos (unlike Reels/videos, see
publishers/meta_reels.py). The repo is already public, so each image is
pushed as a single-file *orphan* commit to a dedicated branch and served
from raw.githubusercontent.com. Each push force-replaces that branch's tip,
so nothing accumulates in git history and the repo never grows -- the image
only needs to stay reachable long enough for Meta to fetch it once, which
happens synchronously within the same run that publishes it (the workflow's
`concurrency` group guarantees no other run starts in the meantime).

Degrades to returning None (Instagram photo post skipped, Facebook unaffected)
if this isn't a git checkout, there's no push access, or anything else fails --
an Instagram photo post is a bonus, never a reason to block or crash a run.
"""
import logging
import os
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import requests

import config

logger = logging.getLogger(__name__)

BRANCH = "public-images"
_BOT_IDENTITY = {
    "GIT_AUTHOR_NAME": "wealthbot", "GIT_AUTHOR_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
    "GIT_COMMITTER_NAME": "wealthbot", "GIT_COMMITTER_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
}
_PROPAGATION_RETRIES = 8
_PROPAGATION_DELAY_SECONDS = 4


class _Result:
    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _git(*args, input_text: str | None = None) -> _Result:
    # Binary stdin/stdout: text=True would translate "\n" to "\r\n" on Windows,
    # which corrupts the tab/newline-delimited input `git mktree` expects.
    result = subprocess.run(
        ["git", *args], cwd=config.BASE_DIR, capture_output=True,
        input=input_text.encode("utf-8") if input_text is not None else None,
        env={**os.environ, **_BOT_IDENTITY},
    )
    return _Result(result.returncode, result.stdout.decode("utf-8", "replace"),
                   result.stderr.decode("utf-8", "replace"))


def _remote_raw_base() -> str | None:
    """Turns the 'origin' remote (https or ssh, with or without embedded credentials)
    into https://raw.githubusercontent.com/<owner>/<repo>."""
    result = _git("remote", "get-url", "origin")
    if result.returncode != 0:
        return None
    url = result.stdout.strip()
    if url.startswith("git@github.com:"):
        slug = url[len("git@github.com:"):]
    else:
        parsed = urlparse(url)
        if parsed.hostname != "github.com":
            return None
        slug = parsed.path.lstrip("/")
    slug = slug[:-4] if slug.endswith(".git") else slug
    return f"https://raw.githubusercontent.com/{slug}" if slug else None


def publish_public_copy(local_path: str) -> str | None:
    """Publishes `local_path` to the public-images branch and returns its raw URL
    once confirmed reachable, or None if it couldn't be published."""
    if _git("rev-parse", "--is-inside-work-tree").returncode != 0:
        logger.info("Not a git checkout; Instagram photo post skipped.")
        return None
    raw_base = _remote_raw_base()
    if not raw_base:
        logger.warning("Could not resolve the git remote; Instagram photo post skipped.")
        return None

    # Pure plumbing (hash-object/mktree/commit-tree/push-by-sha): never touches
    # the working tree, index or HEAD of whatever branch is currently checked out.
    blob = _git("hash-object", "-w", local_path)
    if blob.returncode != 0:
        logger.warning("git hash-object failed: %s", blob.stderr.strip())
        return None
    name = f"{uuid.uuid4().hex}{Path(local_path).suffix}"
    tree = _git("mktree", input_text=f"100644 blob {blob.stdout.strip()}\t{name}\n")
    if tree.returncode != 0:
        logger.warning("git mktree failed: %s", tree.stderr.strip())
        return None
    commit = _git("commit-tree", tree.stdout.strip(), "-m", f"Public image {name}")
    if commit.returncode != 0:
        logger.warning("git commit-tree failed: %s", commit.stderr.strip())
        return None
    push = _git("push", "origin", f"{commit.stdout.strip()}:refs/heads/{BRANCH}", "--force")
    if push.returncode != 0:
        logger.warning("Could not push public image; Instagram photo post skipped. %s", push.stderr.strip())
        return None

    url = f"{raw_base}/{BRANCH}/{name}"
    for _ in range(_PROPAGATION_RETRIES):
        try:
            resp = requests.get(url, timeout=15, stream=True)
            resp.close()
            if resp.status_code == 200:
                return url
        except requests.RequestException:
            pass
        time.sleep(_PROPAGATION_DELAY_SECONDS)
    logger.warning("Public image never became reachable; Instagram photo post skipped.")
    return None
