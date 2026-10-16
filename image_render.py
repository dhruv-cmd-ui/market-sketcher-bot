"""Local FII/DII and news card renderer (Pillow only, no external image API)."""
import datetime
import functools
import uuid

from PIL import Image, ImageDraw, ImageFont

import config

SIZE = 1080
SCALE = 2  # draw at 2x and downscale for anti-aliased edges

BG = (11, 23, 48)
PANEL = (19, 34, 63)
TRACK = (30, 47, 82)
WHITE = (245, 247, 250)
MUTED = (138, 155, 184)
ACCENT = (91, 141, 239)
GREEN = (34, 197, 94)
RED = (239, 68, 68)
GREEN_SOFT = (22, 64, 52)
RED_SOFT = (72, 30, 42)

FONT_PATHS = {
    "inter": config.BASE_DIR / "assets" / "Inter.ttf",
    "montserrat": config.BASE_DIR / "assets" / "Montserrat.ttf",
}
_FALLBACK_FONTS = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def _s(v: float) -> int:
    return int(round(v * SCALE))


@functools.lru_cache(maxsize=None)
def _font(weight: str, size: int, family: str = "inter") -> ImageFont.FreeTypeFont:
    try:
        f = ImageFont.truetype(str(FONT_PATHS[family]), _s(size))
        f.set_variation_by_name(weight)
        return f
    except OSError:
        for path in _FALLBACK_FONTS:
            try:
                return ImageFont.truetype(path, _s(size))
            except OSError:
                continue
        return ImageFont.load_default(_s(size))


def _text(d, xy, text, weight, size, fill, anchor="la", family="inter"):
    d.text((_s(xy[0]), _s(xy[1])), text, font=_font(weight, size, family), fill=fill, anchor=anchor)


def _rrect(d, box, radius, fill):
    d.rounded_rectangle([_s(v) for v in box], radius=_s(radius), fill=fill)


def _inr(value: float) -> str:
    return f"\u20b9{abs(value):,.2f} Cr"


def _bar_row(d, y, label, value, scale_max, color):
    track_x0, track_x1, h = 200, 730, 26
    _text(d, (112, y + h / 2), label, "Medium", 26, MUTED, anchor="lm")
    _rrect(d, (track_x0, y, track_x1, y + h), h / 2, TRACK)
    width = max(h, (track_x1 - track_x0) * value / scale_max)
    _rrect(d, (track_x0, y, track_x0 + width, y + h), h / 2, color)
    _text(d, (968, y + h / 2), _inr(value), "SemiBold", 28, WHITE, anchor="rm")


def _panel(d, top, name, full_name, v, scale_max):
    net = v["net"]
    positive = net >= 0
    color = GREEN if positive else RED
    _rrect(d, (72, top, 1008, top + 300), 28, PANEL)

    _text(d, (112, top + 44), name, "Bold", 44, WHITE)
    _text(d, (112, top + 102), full_name, "Regular", 24, MUTED)

    value_text = ("+" if positive else "\u2212") + _inr(net)
    _text(d, (968, top + 72), value_text, "Bold", 54, color, anchor="rm")

    pill_text = "NET BUY" if positive else "NET SELL"
    pill_font = _font("Bold", 22)
    pill_w = pill_font.getlength(pill_text) / SCALE + 64
    px1, py0 = 968, top + 112
    _rrect(d, (px1 - pill_w, py0, px1, py0 + 40), 20, GREEN_SOFT if positive else RED_SOFT)
    _text(d, (px1 - 22, py0 + 20), pill_text, "Bold", 22, color, anchor="rm")
    # direction triangle inside the pill
    tx, ty = px1 - pill_w + 24, py0 + 20
    tri = [(tx - 9, ty + 6), (tx + 9, ty + 6), (tx, ty - 8)] if positive else \
          [(tx - 9, ty - 6), (tx + 9, ty - 6), (tx, ty + 8)]
    d.polygon([(_s(x), _s(y)) for x, y in tri], fill=color)

    _bar_row(d, top + 186, "Buy", v["buy"], scale_max, GREEN)
    _bar_row(d, top + 240, "Sell", v["sell"], scale_max, RED)


def render_fii_dii_card(report_date: datetime.date, values: dict) -> str:
    img = Image.new("RGB", (_s(SIZE), _s(SIZE)), BG)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, _s(SIZE), _s(8)], fill=ACCENT)
    _text(d, (72, 70), "INSTITUTIONAL FLOWS", "SemiBold", 24, ACCENT)
    _text(d, (72, 104), "FII / DII Activity", "Bold", 68, WHITE)
    _text(d, (72, 196), f"Cash Market  \u00b7  {report_date.strftime('%A, %d %b %Y')}  \u00b7  Provisional",
          "Regular", 27, MUTED)

    scale_max = max(values["fii"]["buy"], values["fii"]["sell"],
                    values["dii"]["buy"], values["dii"]["sell"]) or 1.0
    _panel(d, 268, "FII / FPI", "Foreign Institutional Investors", values["fii"], scale_max)
    _panel(d, 600, "DII", "Domestic Institutional Investors", values["dii"], scale_max)

    d.line([_s(72), _s(948), _s(1008), _s(948)], fill=TRACK, width=_s(2))
    _text(d, (72, 1000), "Source: NSE  \u00b7  Values in \u20b9 Crore", "Regular", 24, MUTED, anchor="lm")
    _text(d, (1008, 1000), "@wealthandworkflow", "SemiBold", 24, ACCENT, anchor="rm")

    return _save(img, f"fii_dii_{report_date.isoformat()}")


def _save(img: Image.Image, stem: str) -> str:
    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    out = config.IMAGES_DIR / f"{stem}_{uuid.uuid4().hex[:6]}.png"
    img.save(out, optimize=True)
    return str(out)


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: float) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if font.getlength(candidate) <= _s(max_width) or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines




NEON = (0, 230, 118)
PILL_YELLOW = (250, 204, 21)
NEWS_LEFT, NEWS_RIGHT = 72, 1008


def _cover_square(img: Image.Image) -> Image.Image:
    w, h = img.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    return img.crop((left, top, left + side, top + side)).resize((_s(SIZE), _s(SIZE)), Image.LANCZOS)


def _fallback_background() -> Image.Image:
    top, bottom = (16, 30, 62), (4, 8, 20)
    column = Image.new("RGB", (1, 256))
    for y in range(256):
        t = y / 255
        column.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return column.resize((_s(SIZE), _s(SIZE)), Image.BILINEAR)


def _dark_overlay(size: tuple[int, int], top: float, bottom: float) -> Image.Image:
    """Vertical black gradient from `top` to `bottom` opacity."""
    mask = Image.new("L", (1, 256))
    for y in range(256):
        mask.putpixel((0, y), int(255 * (top + (bottom - top) * y / 255)))
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    overlay.putalpha(mask.resize(size, Image.BILINEAR))
    return overlay


def _fit_headline(text: str, max_width: float, max_height: float):
    """Largest Montserrat size (78 -> 44) whose wrapped text fits; truncates with an ellipsis at the minimum."""
    for size in range(78, 43, -2):
        lines = _wrap(text, _font("ExtraBold", size, "montserrat"), max_width)
        line_h = size * 1.22
        if len(lines) * line_h <= max_height:
            return lines, size, line_h
    size, line_h = 44, 44 * 1.22
    font = _font("ExtraBold", size, "montserrat")
    lines = _wrap(text, font, max_width)[: int(max_height // line_h)]
    while lines and font.getlength(lines[-1] + "…") > _s(max_width):
        lines[-1] = lines[-1].rsplit(" ", 1)[0]
    lines[-1] += "…"
    return lines, size, line_h


def render_news_card(header: str, headline: str, source: str, date: datetime.date,
                     background: tuple[Image.Image, str, tuple[float, float]] | None = None) -> str:
    """Hybrid card: stock photo (or gradient fallback) + dark overlay + left-aligned headline.
    `background` is (image, credit, overlay opacity range) from backgrounds.get_background()."""
    if background:
        base, credit, (o_top, o_bottom) = _cover_square(background[0]), background[1], background[2]
    else:
        base, credit, (o_top, o_bottom) = _fallback_background(), "", (0.62, 0.82)
    img = Image.alpha_composite(base.convert("RGBA"), _dark_overlay(base.size, o_top, o_bottom))

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    pill_w = _font("ExtraBold", 26, "montserrat").getlength(header) / SCALE + 48
    _rrect(d, (NEWS_LEFT, 72, NEWS_LEFT + pill_w, 128), 12, PILL_YELLOW + (255,))
    _text(d, (NEWS_LEFT + pill_w / 2, 100), header, "ExtraBold", 26, (0, 0, 0, 255),
          anchor="mm", family="montserrat")
    if credit:
        _text(d, (NEWS_RIGHT, 100), credit, "Regular", 18, (255, 255, 255, 150), anchor="rm")

    text_x = NEWS_LEFT + 12 + 32
    area_top, area_bottom = 180, 900
    lines, size, line_h = _fit_headline(" ".join(headline.split()), NEWS_RIGHT - text_x,
                                        area_bottom - area_top)
    block_h = len(lines) * line_h
    block_top = area_top + (area_bottom - area_top - block_h) / 2
    _rrect(d, (NEWS_LEFT, block_top + 6, NEWS_LEFT + 12, block_top + block_h - 6), 6, NEON + (255,))
    y = block_top + line_h / 2
    for line in lines:
        _text(d, (text_x, y), line, "ExtraBold", size, (255, 255, 255, 255),
              anchor="lm", family="montserrat")
        y += line_h

    d.line([_s(NEWS_LEFT), _s(960), _s(NEWS_RIGHT), _s(960)], fill=(255, 255, 255, 70), width=_s(2))
    _text(d, (NEWS_LEFT, 1010), f"{date.strftime('%d %b %Y')}  ·  {source}", "Medium", 24,
          (220, 226, 235, 255), anchor="lm")
    _text(d, (NEWS_RIGHT, 1010), "@wealthandworkflow", "SemiBold", 24, (255, 255, 255, 255), anchor="rm")

    img = Image.alpha_composite(img, layer).convert("RGB")
    return _save(img, f"news_{date.isoformat()}")
