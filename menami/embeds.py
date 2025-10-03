import discord
from .helpers import stars_to_str, iso_utc_to_text
from .config import EMOJIS, CLAIM_WINDOW_S

def format_card_embed(card: dict, claimed: bool) -> discord.Embed:
    ts_text = iso_utc_to_text(card["dropped_at"])
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
    return embed

def build_triple_drop_embed(cards: list[dict]) -> discord.Embed:
    lines = []
    for idx, c in enumerate(cards, start=1):
        stars_str = stars_to_str(int(c["stars"]))
        lines.append(f"{EMOJIS[idx-1]}  {c['card_uid']} · {stars_str} · #{c['serial_number']} · ◈{c['set_id']} · {c['series']} · {c['character']}")
    desc = "**React to claim one card**\n" f"Claim window: {CLAIM_WINDOW_S}s\n\n" + "\n".join(lines)
    return discord.Embed(title="Card Drop — pick with reactions", description=desc, color=discord.Color.blurple())

def build_simple_cardinfo_embed(card: dict) -> discord.Embed:
    stars_str = stars_to_str(int(card["stars"]))
    owner_id = card.get("owned_by")
    owner = f"<@{owner_id}>" if owner_id else "Unowned"

    line = (
        f"{card['card_uid']} · {stars_str} · "
        f"#{card['serial_number']} · ◈{card['set_id']} · "
        f"{card['series']} · {card['character']}"
    )

    e = discord.Embed(title="Card Details", color=discord.Color.blurple())
    e.description = f"Owned by {owner}\n\n{line}"
    return e

def build_character_lookup_embed(stats: dict, edition_index: int) -> discord.Embed:
    e = discord.Embed(title="Character Lookup", color=discord.Color.blurple())

    avg = f"{stats['avg_claim_time']:.1f} seconds" if stats["avg_claim_time"] is not None else "N/A"

    e.description = (
        f"Character · {stats['character']}\n"
        f"Series · {stats['series']}\n"
        f"Wishlisted · 0\n\n"
        f"Total generated · {stats['total_generated']:,}\n"
        f"Total claimed · {stats['total_claimed']:,}\n"
        f"Total burned · {stats['total_burned']:,}\n"
        f"Total in circulation · {stats['total_in_circulation']:,}\n"
        f"Claim rate · {stats['claim_rate']:.0f}%\n"
        f"Average claim time · {avg}\n\n"
        f"Circulation (★★★★) · {stats['circ_by_stars'][4]:,}\n"
        f"Circulation (★★★☆) · {stats['circ_by_stars'][3]:,}\n"
        f"Circulation (★★☆☆) · {stats['circ_by_stars'][2]:,}\n"
        f"Circulation (★☆☆☆) · {stats['circ_by_stars'][1]:,}\n"
        f"Circulation (☆☆☆☆) · {stats['circ_by_stars'][0]:,}\n"
    )

    total_editions = max(len(stats["editions"]), 1)
    e.set_footer(text=f"Showing edition {edition_index} of {total_editions}")
    return e

REWARD_BY_STARS = {0: 1, 1: 5, 2: 12, 3: 35, 4: 75}

def build_burn_preview_embed(requester: discord.abc.User, stars: int) -> discord.Embed:
    coins = REWARD_BY_STARS.get(stars, 0)
    dust = f"✨ 1 Dust ({stars_to_str(stars)})"
    gold = f"💰 {coins} Gold"
    desc = f"{requester.mention}, you will receive:\n\n{gold}\n{dust}"
    return discord.Embed(title="Burn Card", description=desc, color=discord.Color.dark_grey())

def build_burn_result_embed(base: discord.Embed, text: str, color: discord.Color) -> discord.Embed:
    e = discord.Embed(title=base.title, description=base.description + f"\n\n{text}", color=color)
    return e
