import os
import random
import string
import math
import colorsys
from datetime import datetime, timezone
from .config import STAR_MIN, STAR_MAX, QUALITY_BY_STARS, STAR_WEIGHTS

PURE_RED_P   = 0.0005
PURE_WHITE_P = 0.00005
PURE_BLACK_P = 0.00005
ALMOST_PURE_P = 0.0200
NEAR_BLACK_P  = 0.0030
NEAR_WHITE_P  = 0.0040

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

def _hue_of_hex(hex_):
    r, g, b = _hex_to_rgb(hex_)
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    return h, s, v

def _rand(a, b):
    return a + (b - a) * random.random()

def _sample_vivid_midtones():
    h = _rand(0.0, 1.0)
    s = _rand(0.6, 1.0)
    v = _rand(0.55, 0.9)
    return _hsv_to_rgb_hex(h, s, v)

def _sample_pastels_tinted_whites():
    h = _rand(0.0, 1.0)
    s = _rand(0.05, 0.25)
    v = _rand(0.92, 1.0)
    return _hsv_to_rgb_hex(h, s, v)

def _sample_deep_shadows():
    h = _rand(0.0, 1.0)
    s = _rand(0.0, 0.6)
    v = _rand(0.03, 0.15)
    return _hsv_to_rgb_hex(h, s, v)

def _sample_greys_neutrals():
    h = _rand(0.0, 1.0)
    s = _rand(0.0, 0.06)
    v = _rand(0.30, 0.80)
    return _hsv_to_rgb_hex(h, s, v)

def _sample_muted_all_hues():
    h = _rand(0.0, 1.0)
    s = _rand(0.05, 0.25)
    v = _rand(0.40, 0.80)
    return _hsv_to_rgb_hex(h, s, v)

def _sample_earthy_tones():
    h = _rand(0.06, 0.14)
    s = _rand(0.15, 0.5)
    v = _rand(0.30, 0.80)
    return _hsv_to_rgb_hex(h, s, v)

def _sample_metallic_neutrals():
    h = _rand(0.528, 0.667)
    s = _rand(0.05, 0.18)
    v = _rand(0.35, 0.70)
    return _hsv_to_rgb_hex(h, s, v)

def _sample_broken_colors():
    h = _rand(0.0, 1.0)
    s = 0.05 + 0.55 * random.betavariate(1.2, 3.0)
    v = 0.9 - 0.6 * s + _rand(-0.05, 0.05)
    v = max(0.3, min(0.9, v))
    if random.random() < 0.5:
        h = (h + _rand(-0.03, 0.03)) % 1.0
    return _hsv_to_rgb_hex(h, s, v)

def _sample_pure_primaries():
    choices = ["#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff00ff", "#00ffff"]
    return random.choice(choices)

def _mix_undertone(base_hex: str):
    h, s, v = _hue_of_hex(base_hex)
    warm_band = 0.04 <= h <= 0.18
    undertones = [
        ("#8B5A2B", 0.18, 0.10),
        ("#6B7280", 0.16, 0.08),
        ("#556B2F", 0.20, 0.10),
        ("#7D3C98", 0.18, 0.06),
        ("#2F6B6B", 0.16, 0.08),
        ("#A64B2A", 0.18, 0.10),
    ]
    if warm_band:
        undertones = [u for u in undertones if u[0] in ("#6B7280", "#7D3C98", "#2F6B6B")]
    tone_hex, mix_strength, dark_hint = random.choice(undertones)
    if warm_band:
        mix_strength *= 0.5
        dark_hint *= 0.3
    mixed = _mix_hex(base_hex, tone_hex, _rand(mix_strength * 0.7, mix_strength * 1.3))
    if random.random() < 0.9:
        mixed = _mix_hex(mixed, "#000000", _rand(dark_hint * 0.6, dark_hint * 1.4))
    if random.random() < 0.25:
        mixed = _mix_hex(mixed, random.choice(["#B8860B", "#708090"]), 0.08 if not warm_band else 0.04)
    return mixed

def _sample_vivid_nuanced():
    base = _sample_vivid_midtones()
    if random.random() < 0.7:
        return _mix_undertone(base)
    if random.random() < 0.25:
        return _mix_hex(_mix_hex(base, "#B8860B", 0.10), "#000000", 0.05)
    return base

PURITY_SNAP_P = 0.0005
_PURE_PRIMARIES = ["#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff00ff", "#00ffff"]

def _nearest_pure_primary(hex_):
    r, g, b = _hex_to_rgb(hex_)
    best = None
    best_d2 = 1e9
    for p in _PURE_PRIMARIES:
        pr, pg, pb = _hex_to_rgb(p)
        d2 = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best = p
    return best

def _maybe_purify(hex_):
    h, s, v = _hue_of_hex(hex_)
    if s >= 0.98 and v >= 0.98 and random.random() < PURITY_SNAP_P:
        return _nearest_pure_primary(hex_)
    return hex_

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
        return _maybe_purify(_sample_vivid_midtones())
    r -= ALMOST_PURE_P
    if r < NEAR_BLACK_P:
        return _sample_deep_shadows()
    r -= NEAR_BLACK_P
    if r < NEAR_WHITE_P:
        return _sample_pastels_tinted_whites()
    r -= NEAR_WHITE_P
    return _maybe_purify(_sample_vivid_nuanced())

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

async def choose_edition(db) -> int:
    n, weights = await db.get_editions_config()
    editions = list(range(1, n + 1))
    return random.choices(editions, weights=weights, k=1)[0]

async def make_single_card_payload(db, invoker_id: int, guild_id: int) -> dict:
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
