# menami/card_render.py
from __future__ import annotations
import io
from typing import Tuple
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter

CARD_W, CARD_H = 274, 405
PAD = 10
IMG_BOX = (PAD, 70, CARD_W - PAD, CARD_H - 85)

BG_COLOR     = (18, 24, 38)
PANEL_COLOR  = (245, 238, 220)
PANEL_TEXT   = (30, 22, 18)
ACCENT       = (208, 180, 120)

FONT_PATH_BOLD = "assets/fonts/Alkia.ttf"
FONT_PATH_REG  = "assets/fonts/Alkia.ttf"

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
    base = None

    if image_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        base = Image.open(io.BytesIO(data)).convert("RGBA")
        except Exception:
            base = None

    if base is None:
        base = Image.new("RGBA", (274, 405), (245, 245, 245, 255))
    else:
        base = base.resize((274, 405), Image.LANCZOS)

    draw = ImageDraw.Draw(base)

    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except:
        font = ImageFont.load_default()

    draw.text((10, 10), f"{character}", font=font, fill="black")
    draw.text((10, 35), f"{series}", font=font, fill="black")
    draw.text((10, 60), f"#{serial_number} • {set_id}", font=font, fill="black")
    draw.text((10, 85), f"{card_uid}", font=font, fill="black")

    buf = io.BytesIO()
    base.save(buf, format=fmt)
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

