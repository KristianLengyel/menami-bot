from __future__ import annotations
import io
import io as _io_local
from typing import Tuple
import aiohttp
import os
import random
import colorsys
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

CARD_W, CARD_H = 274, 405
CUT_W, CUT_H = 211, 314
PAD = 10
IMG_BOX = (PAD, 70, CARD_W - PAD, CARD_H - 85)

FRAME_CUTOUTS: dict[int, tuple[int, int, int, int]] = {
    1: ((CARD_W - CUT_W) // 2, (CARD_H - CUT_H) // 2, CUT_W, CUT_H),
    2: ((CARD_W - CUT_W) // 2, (CARD_H - CUT_H) // 2, CUT_W, CUT_H),
    3: ((CARD_W - CUT_W) // 2, (CARD_H - CUT_H) // 2, CUT_W, CUT_H),
    4: ((CARD_W - CUT_W) // 2, (CARD_H - CUT_H) // 2, CUT_W, CUT_H),
    5: ((CARD_W - CUT_W) // 2, (CARD_H - CUT_H) // 2, CUT_W, CUT_H),
}

TEXT_BOXES: dict[int, dict[str, tuple[int, int, int, int]]] = {
    5: {"uid": (58, 28, 114, 38), "name": (65, 51, 208, 90), "series": (44, 303, 229, 347), "br": (154, 360, 199, 370)},
    4: {"uid": (62, 27, 117, 36), "name": (61, 47, 212, 90), "series": (50, 301, 223, 352), "br": (159, 361, 215, 372)},
    3: {"uid": (63, 29, 118, 40), "name": (65, 51, 208, 91), "series": (53, 307, 220, 350), "br": (158, 360, 211, 372)},
    2: {"uid": (64, 26, 117, 36), "name": (54, 52, 219, 90), "series": (54, 308, 219, 347), "br": (157, 363, 211, 372)},
    1: {"uid": (57, 28, 111, 40), "name": (59, 53, 214, 91), "series": (59, 310, 214, 348), "br": (164, 359, 219, 371)},
}

BG_COLOR = (18, 24, 38)
PANEL_COLOR = (245, 238, 220)
PANEL_TEXT = (30, 22, 18)
ACCENT = (208, 180, 120)

FONT_PATH_BOLD = "assets/fonts/Alkia.ttf"
FONT_PATH_REG = "assets/fonts/Alkia.ttf"

FRAME_DIR = "assets/frames"

def _text_boxes_for_set(set_id: int) -> tuple[
    tuple[int,int,int,int], tuple[int,int,int,int], tuple[int,int,int,int], tuple[int,int,int,int]
]:
    spec = TEXT_BOXES.get(int(set_id))
    if not spec:
        uid_box = (70, 0, 204, 22)
        name_box = (18, 40, CARD_W - 18, 90)
        series_box = (18, CARD_H - 100, CARD_W - 18, CARD_H - 60)
        br_box = (160, 385, 265, 405)
        return uid_box, name_box, series_box, br_box
    return spec["uid"], spec["name"], spec["series"], spec["br"]

def _cutout_for_set(set_id: int) -> tuple[int, int, int, int]:
    return FRAME_CUTOUTS.get(int(set_id), ((CARD_W - CUT_W) // 2, (CARD_H - CUT_H) // 2, CUT_W, CUT_H))

def _load_frame_for_set(set_id: int) -> Image.Image | None:
    path = os.path.join(FRAME_DIR, f"{int(set_id)}.png")
    if not os.path.exists(path):
        return None
    try:
        im = Image.open(path).convert("RGBA")
        if im.size != (CARD_W, CARD_H):
            im = im.resize((CARD_W, CARD_H), Image.LANCZOS)
        return im
    except Exception:
        return None

async def _fetch_image(url: str) -> Image.Image:
    async with aiohttp.ClientSession() as s:
        async with s.get(url) as r:
            r.raise_for_status()
            b = await r.read()
    return Image.open(io.BytesIO(b)).convert("RGBA")

def _fit_cover(im: Image.Image, box: Tuple[int,int,int,int]) -> Image.Image:
    bw = box[2] - box[0]; bh = box[3] - box[1]
    iw, ih = im.size
    scale = max(bw/iw, bh/ih)
    imr = im.resize((int(iw*scale), int(ih*scale)), Image.LANCZOS)
    iw2, ih2 = imr.size
    left = (iw2 - bw) // 2; top = (ih2 - bh) // 2
    return imr.crop((left, top, left + bw, top + bh))

def _font_try(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def _fit_text_size(draw: ImageDraw.ImageDraw, text: str, font_path: str, max_w: int, max_h: int,
                   size_max: int, size_min: int) -> ImageFont.FreeTypeFont:
    size = size_max
    while size >= size_min:
        f = _font_try(font_path, size)
        tw = draw.textlength(text, font=f)
        th = f.getbbox(text)[3] - f.getbbox(text)[1]
        if tw <= max_w and th <= max_h:
            return f
        size -= 1
    return _font_try(font_path, size_min)

def _draw_centered_fit(draw: ImageDraw.ImageDraw, text: str, rect: tuple[int,int,int,int],
                       font_path: str, size_max: int, size_min: int, fill: tuple[int,int,int,int]):
    l, t, r, b = rect
    max_w = max(1, (r - l) - 2)
    max_h = max(1, (b - t) - 2)
    font = _fit_text_size(draw, text, font_path, max_w, max_h, size_max, size_min)
    tw = draw.textlength(text, font=font)
    th = font.getbbox(text)[3] - font.getbbox(text)[1]
    x = l + (max_w - tw) / 2
    y = t + (max_h - th) / 2
    draw.text((x, y), text, font=font, fill=fill)
    return font

def _round_rect(dst, rect, fill, radius=8, outline=None, outline_width=1):
    x0, y0, x1, y1 = rect
    rr = Image.new("RGBA", (x1-x0, y1-y0), (0,0,0,0))
    d = ImageDraw.Draw(rr)
    d.rounded_rectangle((0,0,rr.width-1, rr.height-1), radius=radius,
                        fill=fill, outline=outline, width=outline_width)
    dst.alpha_composite(rr, (x0,y0))

def _rand_rgb():
    h = random.random()
    r, g, b = colorsys.hsv_to_rgb(h, 0.8, 1.0)
    return (int(r*255), int(g*255), int(b*255))

def _hex_to_rgba(color_hex: str, alpha: int = 255) -> tuple[int,int,int,int]:
    h = color_hex.lstrip("#")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return (r, g, b, alpha)

def _outer_glow_from_frame(frame: Image.Image, cutout_rect: tuple[int,int,int,int],
                           tmin: int = 15, tmax: int = 20, alpha_max: int = 200, color_hex: str | None = None, thickness: int | None = None,) -> Image.Image:
    a = frame.split()[3]
    radius = int(thickness) if thickness is not None else random.randint(tmin, tmax)
    pad = radius * 2
    big = Image.new("L", (a.width + 2*pad, a.height + 2*pad), 0)
    big.paste(a, (pad, pad))
    big_blur = big.filter(ImageFilter.GaussianBlur(radius))
    blur = big_blur.crop((pad, pad, pad + a.width, pad + a.height))
    outer = ImageChops.subtract(blur, a)
    x, y, w, h = cutout_rect
    outside_mask = Image.new("L", a.size, 255)
    ImageDraw.Draw(outside_mask).rectangle([x, y, x+w, y+h], fill=0)
    outer = ImageChops.multiply(outer, outside_mask)
    outer = outer.point(lambda p: min(255, int(p * 1.8)))
    if alpha_max < 255:
        outer = ImageChops.multiply(outer, Image.new("L", outer.size, alpha_max))
    if color_hex:
        color = _hex_to_rgba(color_hex, 255)
    else:
        color = _rand_rgb() + (255,)
    glow = Image.new("RGBA", frame.size, color)
    glow.putalpha(outer)
    return glow

async def render_card_image(
    series: str,
    character: str,
    serial_number: int,
    set_id: int,
    card_uid: str,
    image_url: str | None,
    fmt: str = "PNG",
    apply_glow: bool = False,
    glow_color_hex: str | None = None,
    glow_thickness: int | None = None,
) -> bytes:
    card = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    art = None
    if image_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        art = Image.open(io.BytesIO(data)).convert("RGBA")
        except Exception:
            art = None
    if art is None:
        art = Image.new("RGBA", (CUT_W, CUT_H), (255, 255, 255, 255))
    x, y, w, h = _cutout_for_set(set_id)
    scale = max(w / art.width, h / art.height)
    art = art.resize((int(art.width * scale), int(art.height * scale)), Image.LANCZOS)
    cx = (art.width - w) // 2
    cy = (art.height - h) // 2
    art = art.crop((cx, cy, cx + w, cy + h))
    card.alpha_composite(art, (x, y))
    frame = _load_frame_for_set(set_id)
    if frame is not None:
        if apply_glow:
            glow = _outer_glow_from_frame(frame, (x, y, w, h), 5, 12, 200, glow_color_hex, thickness=glow_thickness)
            card.alpha_composite(glow)
        card.alpha_composite(frame)
    draw = ImageDraw.Draw(card)
    BLACK = (0, 0, 0, 255)
    YELLOW = (255, 215, 64, 255)
    WHITE = (255, 255, 255, 255)
    uid_box, name_box, series_box, br_box = _text_boxes_for_set(set_id)
    _draw_centered_fit(draw, str(character), name_box, FONT_PATH_BOLD, size_max=22, size_min=12, fill=BLACK)
    _draw_centered_fit(draw, str(series), series_box, FONT_PATH_REG, size_max=18, size_min=10, fill=BLACK)
    _draw_centered_fit(draw, str(card_uid).upper(), uid_box, FONT_PATH_REG, size_max=12, size_min=8, fill=YELLOW)
    l, t, r, b = br_box
    max_w = max(1, (r - l) - 2)
    max_h = max(1, (b - t) - 2)
    serial_text = f"#{int(serial_number)} • "
    set_text = str(int(set_id)).upper()
    size_serial = 12
    size_set = 12
    min_serial = 8
    min_set = 7
    while True:
        f_serial = _font_try(FONT_PATH_REG, size_serial)
        f_set = _font_try(FONT_PATH_REG, size_set)
        w_serial = draw.textlength(serial_text, font=f_serial)
        w_set = draw.textlength(set_text, font=f_set)
        h_serial = f_serial.getbbox(serial_text)[3] - f_serial.getbbox(serial_text)[1]
        h_set = f_set.getbbox(set_text)[3] - f_set.getbbox(set_text)[1]
        total_w = w_serial + w_set
        total_h = max(h_serial, h_set)
        if total_w <= max_w and total_h <= max_h:
            break
        if size_serial > min_serial:
            size_serial -= 1
        if size_set > min_set:
            size_set -= 1
        if size_serial == min_serial and size_set == min_set:
            break
    f_serial = _font_try(FONT_PATH_REG, size_serial)
    f_set = _font_try(FONT_PATH_REG, size_set)
    w_serial = draw.textlength(serial_text, font=f_serial)
    w_set = draw.textlength(set_text, font=f_set)
    h_serial = f_serial.getbbox(serial_text)[3] - f_serial.getbbox(serial_text)[1]
    h_set = f_set.getbbox(set_text)[3] - f_set.getbbox(set_text)[1]
    total_w = w_serial + w_set
    total_h = max(h_serial, h_set)
    x_start = l + (max_w - total_w) / 2
    y_start = t + (max_h - total_h) / 2
    draw.text((x_start, y_start), serial_text, font=f_serial, fill=YELLOW)
    draw.text((x_start + w_serial, y_start), set_text, font=f_set, fill=WHITE)
    buf = io.BytesIO()
    card.save(buf, format=fmt)
    return buf.getvalue()

async def render_drop_triptych(db, cards: list[dict]) -> bytes:
    target_w, target_h = 836, 419
    padding = 20
    available_w = target_w - (2 * padding)
    available_h = target_h - (2 * padding)
    orig_w, orig_h = 274, 405
    scale = min(available_h / orig_h, (available_w / 3) / orig_w)
    card_w, card_h = int(orig_w * scale), int(orig_h * scale)
    total_card_w = card_w * 3
    remaining_w = target_w - total_card_w
    gap = remaining_w // 4
    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    rendered_images: list[Image.Image] = []
    for c in cards:
        url = await db.get_character_image(c["series"], c["character"], int(c["set_id"]))
        if not url:
            url = await db.get_character_image_any(c["series"], c["character"])
        img_bytes = await render_card_image(
            series=c["series"],
            character=c["character"],
            serial_number=int(c["serial_number"]),
            set_id=int(c["set_id"]),
            card_uid=c["card_uid"],
            image_url=url,
            fmt="PNG",
            apply_glow=False,
        )
        im = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        im = im.resize((card_w, card_h), Image.LANCZOS)
        rendered_images.append(im)
    y = (target_h - card_h) // 2
    x = gap
    for im in rendered_images:
        canvas.alpha_composite(im, (x, y))
        x += card_w + gap
    out = io.BytesIO()
    canvas.save(out, format="WEBP")
    return out.getvalue()

async def render_dye_preview(before_bytes: bytes, after_bytes: bytes) -> bytes:
    left = Image.open(_io_local.BytesIO(before_bytes)).convert("RGBA")
    right = Image.open(_io_local.BytesIO(after_bytes)).convert("RGBA")
    h = max(left.height, right.height)
    left = left.resize((int(left.width * (h / left.height)), h), Image.LANCZOS)
    right = right.resize((int(right.width * (h / right.height)), h), Image.LANCZOS)

    arrow_w = 64
    arrow = Image.new("RGBA", (arrow_w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(arrow)
    cx = arrow_w // 2
    d.polygon([(cx - 16, h//2 - 20), (cx - 16, h//2 + 20), (cx + 16, h//2)], fill=(200, 0, 200, 220))

    pad = 16
    out = Image.new("RGBA", (left.width + arrow_w + right.width + pad * 4, h + pad * 2), (0, 0, 0, 0))
    x = pad
    out.alpha_composite(left, (x, pad)); x += left.width + pad
    out.alpha_composite(arrow, (x, pad)); x += arrow_w + pad
    out.alpha_composite(right, (x, pad))

    buf = _io_local.BytesIO()
    out.save(buf, format="WEBP")
    return buf.getvalue()