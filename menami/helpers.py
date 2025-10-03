import os
import random
import string
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
