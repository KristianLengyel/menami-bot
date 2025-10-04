from __future__ import annotations
import io
from typing import Tuple
import aiohttp
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

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
    1: {  # 1.png
        "uid": (55 - 15, 5 + 5, 189 - 15, 25 + 5),
        "br":  (145 - 15, 370 - 15, 250 - 15, 390 - 15),
    },
    2: {  # 2.png
        "uid": (50 - 15, 5 + 5, 195 - 15, 27 + 5),
        "br":  (145 - 15, 370 - 15, 250 - 15, 390 - 15),
    },
    3: {  # 3.png
        "uid": (45 - 15, 5 + 5, 200 - 15, 27 + 5),
        "br":  (145 - 15, 370 - 15, 250 - 15, 390 - 15),
    },
    4: {  # 4.png
        "uid": (43 - 15, 5 + 5, 201 - 15, 27 + 5),
        "br":  (145 - 15, 370 - 15, 250 - 15, 390 - 15),
    },
    5: {  # 5.png
        "uid": (49 - 15, 5 + 5, 195 - 15, 29 + 5),
        "br":  (145 - 15, 370 - 15, 250 - 15, 390 - 15),
    },
}

BG_COLOR     = (18, 24, 38)
PANEL_COLOR  = (245, 238, 220)
PANEL_TEXT   = (30, 22, 18)
ACCENT       = (208, 180, 120)

FONT_PATH_BOLD = "assets/fonts/Alkia.ttf"
FONT_PATH_REG  = "assets/fonts/Alkia.ttf"

FRAME_DIR = "assets/frames"

def _text_boxes_for_set(set_id: int) -> tuple[tuple[int,int,int,int], tuple[int,int,int,int]]:
    spec = TEXT_BOXES.get(int(set_id))
    if not spec:
        uid_box = (70, 0, 204, 22)
        br_box  = (160, 385, 265, 405)
        return uid_box, br_box
    return spec["uid"], spec["br"]

def _cutout_for_set(set_id: int) -> tuple[int, int, int, int]:
    return FRAME_CUTOUTS.get(int(set_id), ((CARD_W - CUT_W) // 2, (CARD_H - CUT_H) // 2, CUT_W, CUT_H))

def _load_frame_for_set(set_id: int) -> Image.Image | None:
    import os
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

def _shadow(rect, radius=8, spread=4):
    x0,y0,x1,y1 = rect
    w, h = x1-x0, y1-y0
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0,0,w-1,h-1), radius=radius, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(spread))

def _round_rect(dst, rect, fill, radius=8, outline=None, outline_width=1):
    x0,y0,x1,y1 = rect
    rr = Image.new("RGBA", (x1-x0, y1-y0), (0,0,0,0))
    d = ImageDraw.Draw(rr)
    d.rounded_rectangle((0,0,rr.width-1, rr.height-1), radius=radius,
                        fill=fill, outline=outline, width=outline_width)
    dst.alpha_composite(rr, (x0,y0))

def _truncate(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    ell = "…"
    while text and draw.textlength(text + ell, font=font) > max_w:
        text = text[:-1]
    return text + ell

async def render_card_image(series: str, character: str, serial_number: int, set_id: int,
                            card_uid: str, image_url: str | None, fmt="PNG") -> bytes:
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
        art = Image.new("RGBA", (CUT_W, CUT_H), (230, 230, 230, 255))

    x, y, w, h = _cutout_for_set(set_id)
    scale = max(w / art.width, h / art.height)
    art = art.resize((int(art.width * scale), int(art.height * scale)), Image.LANCZOS)
    cx = (art.width - w) // 2
    cy = (art.height - h) // 2
    art = art.crop((cx, cy, cx + w, cy + h))
    card.alpha_composite(art, (x, y))

    frame = _load_frame_for_set(set_id)
    if frame is not None:
        card.alpha_composite(frame)

    draw = ImageDraw.Draw(card)
    try:
        font_name   = ImageFont.truetype(FONT_PATH_BOLD, 22)
        font_series = ImageFont.truetype(FONT_PATH_REG, 18)
        font_uid    = ImageFont.truetype(FONT_PATH_REG, 14)
        font_small  = ImageFont.truetype(FONT_PATH_REG, 12)
    except Exception:
        font_name = font_series = font_uid = font_small = ImageFont.load_default()

    BLACK  = (0, 0, 0, 255)
    YELLOW = (255, 215, 64, 255)
    WHITE  = (255, 255, 255, 255)

    name_rect   = (18, 40, CARD_W - 18, 90)
    series_rect = (18, CARD_H - 100, CARD_W - 18, CARD_H - 60)

    def draw_centered(text: str, rect, font, fill):
        l, t, r, b = rect
        s = _truncate(draw, text, font, r - l - 10)
        tw = draw.textlength(s, font=font)
        th = font.getbbox(s)[3] - font.getbbox(s)[1]
        tx = l + (r - l - tw) / 2
        ty = t + (b - t - th) / 2
        draw.text((tx, ty), s, font=font, fill=fill)

    draw_centered(str(character), name_rect, font_name, BLACK)

    draw_centered(str(series), series_rect, font_series, BLACK)

    uid_box, br_box = _text_boxes_for_set(set_id)
    draw_centered(str(card_uid), uid_box, font_uid, YELLOW)

    l, t, r, b = br_box
    serial_text = f"#{int(serial_number)} • "
    set_text    = f"{int(set_id)}"
    w_serial = draw.textlength(serial_text, font=font_small)
    w_set    = draw.textlength(set_text, font=font_small)
    total_w  = w_serial + w_set
    x_start = r - total_w
    y_mid = t + (b - t - (font_small.getbbox("A")[3] - font_small.getbbox("A")[1])) / 2

    draw.text((x_start, y_mid), serial_text, font=font_small, fill=YELLOW)
    draw.text((x_start + w_serial, y_mid), set_text, font=font_small, fill=WHITE)

    buf = io.BytesIO()
    card.save(buf, format=fmt)
    return buf.getvalue()

# --- for /drop (836x419 WEBP) ---

async def render_drop_triptych(db, cards: list[dict]) -> bytes:
    import io
    from PIL import Image

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

