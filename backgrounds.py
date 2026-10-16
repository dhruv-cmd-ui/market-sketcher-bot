"""News-card backgrounds, generated locally (no API, no rate limits, no watermark).

Order: a random photo from assets/backgrounds/ if any are present, otherwise a
procedurally drawn abstract fintech scene (gradient, glow, grid, price chart).
"""
import hashlib
import logging
import random

from PIL import Image, ImageDraw, ImageFilter

import config

logger = logging.getLogger(__name__)

_LOCAL_DIR = config.BASE_DIR / "assets" / "backgrounds"
SIZE = 2160
# Photos are busy, so they get the full ~70% dark overlay; the generated art is dark by design.
PHOTO_OVERLAY = (0.62, 0.82)
PROCEDURAL_OVERLAY = (0.25, 0.60)

# (dark corner, mid corner, accent) per theme
_THEMES = [
    ((6, 14, 38), (12, 52, 96), (0, 200, 255)),     # midnight / electric blue
    ((4, 24, 22), (8, 70, 60), (0, 230, 118)),       # deep green / neon green
    ((18, 8, 40), (60, 24, 110), (190, 90, 255)),    # indigo / violet
    ((8, 16, 36), (24, 40, 90), (255, 196, 0)),      # navy / gold
]


def _gradient(rng: random.Random, dark, mid) -> Image.Image:
    corners = [dark, mid, dark, dark]
    rng.shuffle(corners)
    tiny = Image.new("RGB", (2, 2))
    for (x, y), c in zip([(0, 0), (1, 0), (0, 1), (1, 1)], corners):
        tiny.putpixel((x, y), c)
    return tiny.resize((SIZE, SIZE), Image.BICUBIC)


def _glow_blobs(rng, accent, mid) -> Image.Image:
    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(rng.randint(4, 6)):
        r = rng.randint(250, 650)
        cx, cy = rng.randint(0, SIZE), rng.randint(0, SIZE)
        color = accent if rng.random() < 0.5 else mid
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (rng.randint(130, 190),))
    return layer.filter(ImageFilter.GaussianBlur(200))


def _grid() -> Image.Image:
    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for v in range(0, SIZE, 120):
        d.line([(v, 0), (v, SIZE)], fill=(255, 255, 255, 22), width=2)
        d.line([(0, v), (SIZE, v)], fill=(255, 255, 255, 22), width=2)
    return layer


def _price_path(rng) -> list[tuple[float, float]]:
    points, y = [], rng.uniform(SIZE * 0.55, SIZE * 0.75)
    trend = rng.uniform(-4, 6)
    for i in range(61):
        y = min(SIZE * 0.88, max(SIZE * 0.30, y - trend + rng.gauss(0, 38)))
        points.append((i * SIZE / 60, y))
    return points


def _chart(rng, accent) -> tuple[Image.Image, Image.Image]:
    path = _price_path(rng)
    fill = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(fill).polygon(path + [(SIZE, SIZE), (0, SIZE)], fill=accent + (60,))

    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(glow).line(path, fill=accent + (230,), width=44, joint="curve")
    glow = glow.filter(ImageFilter.GaussianBlur(28))

    line = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ld = ImageDraw.Draw(line)
    ld.line(path, fill=accent + (255,), width=11, joint="curve")

    # faint candlesticks along the chart
    for i in range(2, 60, 2):
        x, y = path[i]
        up = path[i + 1][1] < y
        color = (34, 197, 94, 170) if up else (239, 68, 68, 170)
        body = rng.uniform(30, 90)
        wick = body + rng.uniform(20, 60)
        ld.line([(x, y - wick), (x, y + wick)], fill=color, width=4)
        ld.rectangle([x - 14, y - body / 2, x + 14, y + body / 2], fill=color)
    return Image.alpha_composite(Image.alpha_composite(fill, glow), line), fill


def _procedural(seed_text: str) -> Image.Image:
    rng = random.Random(int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest(), 16))
    dark, mid, accent = rng.choice(_THEMES)
    img = _gradient(rng, dark, mid).convert("RGBA")
    img = Image.alpha_composite(img, _glow_blobs(rng, accent, mid))
    img = Image.alpha_composite(img, _grid())
    chart, _ = _chart(rng, accent)
    img = Image.alpha_composite(img, chart)
    return img.convert("RGB")


def _from_local_folder() -> Image.Image | None:
    if not _LOCAL_DIR.is_dir():
        return None
    files = [p for p in _LOCAL_DIR.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    if not files:
        return None
    try:
        return Image.open(random.choice(files)).convert("RGB")
    except Exception:
        logger.warning("Could not open local background image.", exc_info=True)
        return None


def get_background(seed_text: str) -> tuple[Image.Image, str, tuple[float, float]]:
    """Returns (image, credit text, overlay opacity top->bottom). `seed_text` (e.g. the headline) makes the
    procedural scene unique per post but reproducible."""
    local = _from_local_folder()
    if local is not None:
        return local, "", PHOTO_OVERLAY
    return _procedural(seed_text), "", PROCEDURAL_OVERLAY
