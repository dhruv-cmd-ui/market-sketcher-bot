"""Animated 9:16 Reels (with music + SFX), rendered locally with HyperFrames."""
import datetime
import json
import logging
import shutil
import subprocess
import tempfile
import threading
import uuid

from PIL import Image

import config

logger = logging.getLogger(__name__)

HYPERFRAMES = "hyperframes@0.8.164"  # pinned so renders stay identical over time
FII_DII_PROJECT = config.BASE_DIR / "reels" / "fii_dii"
NEWS_PROJECT = config.BASE_DIR / "reels" / "news"
RENDER_TIMEOUT_SECONDS = 600


# News and FII/DII jobs run in separate threads; each render launches several
# Chrome processes, so two at once can exhaust RAM on a small VPS.
_render_lock = threading.Lock()


def _render(project_dir, variables: dict, stem: str) -> str:
    with _render_lock:
        return _render_unlocked(project_dir, variables, stem)


def _render_unlocked(project_dir, variables: dict, stem: str) -> str:
    npx = shutil.which("npx")
    if not npx:
        raise RuntimeError("npx not found; install Node.js 22+ to render reels")
    out = config.IMAGES_DIR / f"{stem}_{uuid.uuid4().hex[:6]}.mp4"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(variables, f)
        vars_path = f.name
    cmd = [npx, "--yes", HYPERFRAMES, "render", str(project_dir), "-o", str(out),
           "--quality", "delivery", "--variables-file", vars_path, "--strict-variables", "--quiet"]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=RENDER_TIMEOUT_SECONDS)
    if result.returncode != 0 or not out.exists():
        raise RuntimeError(f"HyperFrames render failed ({result.returncode}): {result.stderr[-2000:]}")
    return str(out)


def render_fii_dii_reel(report_date: datetime.date, values: dict) -> str:
    fii, dii = values["fii"], values["dii"]
    return _render(FII_DII_PROJECT, {
        "date_label": report_date.strftime("%A, %d %b %Y"),
        "fii_buy": fii["buy"], "fii_sell": fii["sell"], "fii_net": fii["net"],
        "dii_buy": dii["buy"], "dii_sell": dii["sell"], "dii_net": dii["net"],
    }, f"fii_dii_reel_{report_date.isoformat()}")


def render_news_reel(header: str, headline: str, source: str, date: datetime.date,
                     background: Image.Image) -> str:
    # The composition can only load files inside its project folder.
    bg_name = f"bg_{uuid.uuid4().hex[:8]}.jpg"
    bg_path = NEWS_PROJECT / "assets" / bg_name
    background.convert("RGB").save(bg_path, quality=90)
    try:
        return _render(NEWS_PROJECT, {
            "header": header,
            "headline": " ".join(headline.split()),
            "source": source,
            "date_label": date.strftime("%d %b %Y"),
            "bg_src": f"assets/{bg_name}",
        }, f"news_reel_{date.isoformat()}")
    finally:
        bg_path.unlink(missing_ok=True)
