import os
import random
import string
from datetime import datetime, timezone
import discord

from .config import STAR_MIN, STAR_MAX, QUALITY_BY_STARS, CLAIM_WINDOW_S, EMOJIS

def gen_card_uid():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=7))

def stars_to_str(n):
    n = max(0, min(4, int(n)))
    return "★" * n + "☆" * (4 - n)

def _format_timestamp_iso_utc_to_text(iso_str: str):
    dt = datetime.fromisoformat(iso_str).replace(tzinfo=timezone.utc)
    if os.name == "nt":
        return dt.strftime("%B %#d, %Y %#I:%M %p")
    return dt.strftime("%B %-d, %Y %-I:%M %p")

def format_card_embed(card: dict, claimed: bool):
    ts_text = _format_timestamp_iso_utc_to_text(card["dropped_at"])
    owner = f"<@{card['owned_by']}>" if card["owned_by"] else "—"
    grabbed = f"<@{card['grabbed_by']}>" if card["grabbed_by"] else "—"
    dropped_by = f"<@{card['dropped_by']}>"
    stars_str = stars_to_str(int(card["stars"]))

    uid_box    = f"`{card['card_uid']}`"
    stars_box  = f"`{stars_str}`"
    serial_box = f"`#{card['serial_number']}`"
    setid_box  = f"`◈{card['set_id']}`"
    server_box = f"`{card['dropped_in_server']}`"

    title = f"{uid_box} · {stars_box} · {serial_box} · {setid_box} · {card['series']} · **{card['character']}**"

    desc_lines = [
        f"Dropped on **{ts_text}**",
        f"Dropped in server ID {server_box}",
        "",
        f"Owned by {owner}",
        f"Grabbed by {grabbed}",
        f"Dropped by {dropped_by}",
        "",
        f"Dropped in **{card['condition']}** condition",
    ]
    if card["grab_delay"] is not None:
        desc_lines.append(f"Grabbed after **{float(card['grab_delay']):.2f} seconds**")

    embed = discord.Embed(
        title="Card Details",
        description="\n".join([title, "", *desc_lines]),
        color=discord.Color.gold()
    )
    if claimed and card["grab_delay"] is None:
        embed.set_footer(text="Claim processed.")
    return embed

def build_triple_drop_embed(cards: list[dict]):
    lines = []
    for idx, c in enumerate(cards, start=1):
        stars_str = stars_to_str(int(c["stars"]))
        lines.append(f"{EMOJIS[idx-1]}  {c['card_uid']} · {stars_str} · #{c['serial_number']} · ◈{c['set_id']} · {c['series']} · {c['character']}")
    desc = "**React to claim one card**\n" f"Claim window: {CLAIM_WINDOW_S}s\n\n" + "\n".join(lines)
    return discord.Embed(title="Card Drop — pick with reactions", description=desc, color=discord.Color.blurple())

async def choose_edition(db) -> int:
    n, weights = await db.get_editions_config()
    editions = list(range(1, n + 1))
    return random.choices(editions, weights=weights, k=1)[0]

async def make_single_card_payload(db, invoker_id: int, guild_id: int):
    set_id = await choose_edition(db)
    sc = await db.random_series_character()
    if not sc:
        series, character = ("Unknown Series", "Unknown Character")
    else:
        series, character = sc
    stars = random.randint(STAR_MIN, STAR_MAX)
    condition = QUALITY_BY_STARS.get(int(stars), "damaged")
    dropped_at = datetime.utcnow().isoformat()
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
