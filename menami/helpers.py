import os
import random
import string
import math
from datetime import datetime, timezone
from .config import STAR_MIN, STAR_MAX, QUALITY_BY_STARS, STAR_WEIGHTS

def gen_card_uid() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=7))

def stars_to_str(n: int) -> str:
    n = max(0, min(4, int(n)))
    return "★" * n + "☆" * (4 - n)

def iso_utc_to_text(iso_str: str) -> str:
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if os.name == "nt":
        return dt.strftime("%B %#d, %Y %#I:%M %p")
    return dt.strftime("%B %-d, %Y %-I:%M %p")

async def choose_edition(db) -> int:
    n, weights = await db.get_editions_config()
    editions = list(range(1, n + 1))
    return random.choices(editions, weights=weights, k=1)[0]

async def make_single_card_payload(db, invoker_id: int, guild_id: int) -> dict:
    from .config import STAR_MIN, STAR_MAX, STAR_WEIGHTS, QUALITY_BY_STARS
    set_id = await choose_edition(db)
    sc = await db.random_series_character()
    if not sc:
        series, character = ("Unknown Series", "Unknown Character")
    else:
        series, character = sc
    domain = list(range(STAR_MIN, STAR_MAX + 1))
    try:
        if len(STAR_WEIGHTS) != len(domain) or any(float(w) <= 0 for w in STAR_WEIGHTS):
            raise ValueError
        stars = int(random.choices(domain, weights=STAR_WEIGHTS, k=1)[0])
    except Exception:
        stars = int(random.randint(STAR_MIN, STAR_MAX))
    condition = QUALITY_BY_STARS.get(int(stars), "damaged")
    dropped_at = datetime.now(timezone.utc).isoformat()
    return {
        "card_uid": gen_card_uid(),
        "serial_number": None,
        "stars": stars,
        "set_id": set_id,
        "series": series,
        "character": character,
        "condition": condition,
        "dropped_at": dropped_at,
        "dropped_in_server": str(guild_id),
        "dropped_by": str(invoker_id),
    }

def _base36(n: int) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if n == 0:
        return "0"
    s = ""
    while n:
        n, r = divmod(n, 36)
        s = chars[r] + s
    return s

def generate_dye_code() -> str:
    x = random.getrandbits(30)
    core = _base36(x).lower()
    core = ("vv" + core).ljust(6, "0")[:6]
    return f"${core}"

def _hsv_to_rgb_hex(h: float, s: float, v: float) -> str:
    i = int(h * 6.0) % 6
    f = h * 6.0 - int(h * 6.0)
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q
    return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))

def random_color_hex_with_weights() -> str:
    r = random.random()
    if r < 0.006:
        return "#ff0000"
    if r < 0.010:
        return "#ffffff"
    if r < 0.014:
        return "#000000"
    h = random.random()
    s = 0.55 + random.random() * 0.4
    v = 0.6 + random.random() * 0.35
    return _hsv_to_rgb_hex(h, s, v)

_ADJ = ["Mystic","Lovely","Euphoric","Barbarian","Azure","Crimson","Ivory","Obsidian","Wizard","Romantic","Vice","Celestial","Neon","Frosted","Dusky","Radiant","Velvet","Phantom","Atomic","Retro"]
_NOUN = ["Petal","Plush","Delight","Flesh","Atoll","Blue","City","Eclipse","Glow","Dream","Ember","Whisper","Charm","Mirage","Pulse","Velour","Dawn","Twilight","Storm","Bloom"]

def dye_name_from_seed(code: str, color_hex: str) -> str:
    seed = sum(ord(c) for c in (code + color_hex))
    a = _ADJ[seed % len(_ADJ)]
    b = _NOUN[(seed // 7) % len(_NOUN)]
    c = _NOUN[(seed // 37) % len(_NOUN)]
    if b == c:
        c = _ADJ[(seed // 11) % len(_ADJ)]
    return f"{a} {b} {c}"

def _hex_to_rgb(color_hex: str) -> tuple[int, int, int]:
    hx = color_hex.lstrip("#")
    return int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)

def circle_name_for_color(color_hex: str) -> str:
    r, g, b = _hex_to_rgb(color_hex)
    if r < 28 and g < 28 and b < 28:
        return "black"
    if r > 227 and g > 227 and b > 227:
        return "white"
    num = (g - b) * 0.8660254037844386
    den = 2 * r - g - b
    hue = math.atan2(num, den)
    hue = (hue + 2 * math.pi) % (2 * math.pi)
    h = hue / (2 * math.pi)
    v = max(r, g, b) / 255.0
    s = 0 if v == 0 else 1 - (min(r, g, b) / 255.0) / v
    if 0.04 <= h < 0.14:
        if v < 0.65 and s > 0.5:
            return "brown"
    if h < 1/12 or h >= 11/12:
        return "red"
    if h < 3/12:
        return "orange"
    if h < 5/12:
        return "yellow"
    if h < 7/12:
        return "green"
    if h < 9/12:
        return "blue"
    return "purple"

def emoji_shortcode_for_color(color_hex: str) -> str:
    name = circle_name_for_color(color_hex)
    return f":{name}_circle:"
