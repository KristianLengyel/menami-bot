import os
import random
import string
import math
import colorsys
from datetime import datetime, timezone
from .config import STAR_MIN, STAR_MAX, QUALITY_BY_STARS, STAR_WEIGHTS

# === Rarity controls ===
PURE_RED_P = 0.0005    # 0.05% (≈50 per 100k)
PURE_WHITE_P = 0.00005 # 0.005% (≈5 per 100k)
PURE_BLACK_P = 0.00005 # 0.005% (≈5 per 100k)
ALMOST_PURE_P = 0.0200 # 2.00%
NEAR_BLACK_P = 0.0030  # 0.30%
NEAR_WHITE_P = 0.0040  # 0.40%
TINTED_WHITE_P = 0.0120# 1.20%
GREYISH_P = 0.0100     # 1.00%
WARM_BRIGHT_OVERRIDE_P = 0.0300

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

def _clamp8(x: float) -> int:
    return max(0, min(255, int(round(x))))

def _rgb_to_hex(r: float, g: float, b: float) -> str:
    return "#{:02x}{:02x}{:02x}".format(_clamp8(r), _clamp8(g), _clamp8(b))

def _hex_to_rgb(color_hex: str) -> tuple[int, int, int]:
    hx = color_hex.lstrip("#")
    return int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)

def _mix_hex(a: str, b: str, ratio: float) -> str:
    ratio = max(0.0, min(1.0, float(ratio)))
    ar, ag, ab = _hex_to_rgb(a)
    br, bg, bb = _hex_to_rgb(b)
    r = ar * (1 - ratio) + br * ratio
    g = ag * (1 - ratio) + bg * ratio
    b = ab * (1 - ratio) + bb * ratio
    return _rgb_to_hex(r, g, b)

def _darken_hex(a: str, amount: float) -> str:
    return _mix_hex(a, "#000000", max(0.0, min(1.0, amount)))

def _hue_of_hex(hex_):
    r, g, b = _hex_to_rgb(hex_)
    h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
    return h, s, v

def _random_base_hsv_hex() -> str:
    if random.random() < WARM_BRIGHT_OVERRIDE_P:
        h = random.uniform(0.04, 0.18)
        s = random.uniform(0.92, 0.99)
        v = random.uniform(0.95, 1.00)
        return _hsv_to_rgb_hex(h, s, v)
    h = random.random()
    s = 0.55 + random.random() * 0.40
    v = 0.60 + random.random() * 0.35
    return _hsv_to_rgb_hex(h, s, v)

def _almost_pure_hsv_hex(h: float, dh: float = 0.01) -> str:
    h = (h + random.uniform(-dh, dh)) % 1.0
    s = random.uniform(0.94, 0.995)
    v = random.uniform(0.94, 0.995)
    return _hsv_to_rgb_hex(h, s, v)

def _near_black_hex() -> str:
    h = random.random()
    s = random.uniform(0.55, 1.0)
    v = random.uniform(0.02, 0.10)
    return _hsv_to_rgb_hex(h, s, v)

def _near_white_hex() -> str:
    h = random.random()
    s = random.uniform(0.02, 0.12)
    v = random.uniform(0.94, 0.99)
    return _hsv_to_rgb_hex(h, s, v)

def _tinted_white_hex() -> str:
    anchors = [0.00, 1/12, 1/6, 0.20, 2/6, 0.40, 3/6, 4/6, 0.72, 5/6, 0.90, 11/12]
    h_anchor = random.choice(anchors)
    h = (h_anchor + random.uniform(-0.015, 0.015)) % 1.0
    s = random.uniform(0.04, 0.18)
    v = random.uniform(0.95, 0.995)
    return _hsv_to_rgb_hex(h, s, v)

def _greyish_hex() -> str:
    g = random.uniform(0.25, 0.85)
    base = "#{:02x}{:02x}{:02x}".format(int(g*255), int(g*255), int(g*255))
    if random.random() < 0.6:
        tint = random.choice(["#B8860B", "#708090", "#6B7280", "#A0A0A0"])
        amt = random.uniform(0.04, 0.18)
        return _mix_hex(base, tint, amt)
    return base

def _random_color_hex_nuanced() -> str:
    base = _random_base_hsv_hex()
    h, s, v = _hue_of_hex(base)
    warm_band = 0.04 <= h <= 0.18

    undertones = [
        ("tortoise", "#8B5A2B", 0.18, 0.10),
        ("smoke",    "#6B7280", 0.16, 0.08),
        ("moss",     "#556B2F", 0.20, 0.10),
        ("plum",     "#7D3C98", 0.18, 0.06),
        ("tealgray", "#2F6B6B", 0.16, 0.08),
        ("ember",    "#A64B2A", 0.18, 0.10),
    ]

    if warm_band:
        undertones = [u for u in undertones if u[0] in ("smoke", "plum", "tealgray")]
    if random.random() < 0.70:
        _, tone_hex, mix_strength, dark_hint = random.choice(undertones)
        if warm_band:
            mix_strength *= 0.50
            dark_hint *= 0.30
        mixed = _mix_hex(base, tone_hex, random.uniform(mix_strength * 0.7, mix_strength * 1.3))
        if random.random() < 0.90:
            mixed = _darken_hex(mixed, random.uniform(dark_hint * 0.6, dark_hint * 1.4))
        if random.random() < 0.25:
            amt = 0.08 if not warm_band else 0.04
            mixed = _mix_hex(mixed, random.choice(["#B8860B", "#708090"]), amt)
        return mixed
    if random.random() < 0.25:
        antique = _mix_hex(base, "#B8860B", 0.10 if not warm_band else 0.04)
        return _darken_hex(antique, 0.05 if not warm_band else 0.02)
    return base

def random_color_hex_with_weights() -> str:
    r = random.random()
    if r < PURE_RED_P:
        return "#ff0000"
    r -= PURE_RED_P
    if r < PURE_WHITE_P:
        return "#ffffff"
    r -= PURE_WHITE_P
    if r < PURE_BLACK_P:
        return "#000000"
    r -= PURE_BLACK_P
    if r < ALMOST_PURE_P:
        bucket = random.choice([0.0, 1/12, 1/6, 2/6, 3/6, 4/6, 5/6])
        return _almost_pure_hsv_hex(bucket)
    r -= ALMOST_PURE_P
    if r < NEAR_BLACK_P:
        return _near_black_hex()
    r -= NEAR_BLACK_P
    if r < NEAR_WHITE_P:
        return _near_white_hex()
    r -= NEAR_WHITE_P
    if r < TINTED_WHITE_P:
        return _tinted_white_hex()
    r -= TINTED_WHITE_P
    if r < GREYISH_P:
        return _greyish_hex()
    return _random_color_hex_nuanced()

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

def circle_name_for_color(color_hex: str) -> str:
    r, g, b = _hex_to_rgb(color_hex)
    v = max(r, g, b) / 255.0
    s = 0 if v == 0 else 1 - (min(r, g, b) / 255.0) / v
    if v <= 0.12:
        return "black"
    if v >= 0.92 and s <= 0.15:
        return "white"
    num = (g - b) * 0.8660254037844386
    den = 2 * r - g - b
    hue = math.atan2(num, den)
    hue = (hue + 2 * math.pi) % (2 * math.pi)
    h = hue / (2 * math.pi)
    if 0.04 <= h < 0.14 and v < 0.65 and s > 0.5:
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
