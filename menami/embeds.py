import discord
from .helpers import stars_to_str, iso_utc_to_text
from .config import QUALITY_BY_STARS, BURN_REWARD_BY_STARS, UPGRADE_RULES

# ========= Card detail & drops =========

def format_card_embed(card: dict, claimed: bool):
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
        try:
            desc_lines.append(f"Grabbed after **{float(card['grab_delay']):.2f} seconds**")
        except Exception:
            pass

    embed = discord.Embed(
        title="Card Details",
        description="\n".join([title, "", *desc_lines]),
        color=discord.Color.gold()
    )
    if claimed and card["grab_delay"] is None:
        embed.set_footer(text="Claim processed.")
    return embed

def build_triple_drop_embed(cards: list[dict]):
    from .config import EMOJIS, CLAIM_WINDOW_S
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
    set_id = stats.get("set_id")
    if set_id is None:
        e.set_footer(text=f"All editions • {edition_index}/{total_editions}")
    else:
        e.set_footer(text=f"Edition ◈{set_id} • {edition_index}/{total_editions}")
    return e

# ========= Burn embeds =========

def build_burn_preview_embed(requester: discord.abc.User, stars: int) -> discord.Embed:
    coins = BURN_REWARD_BY_STARS.get(stars, 0)
    dust = f"1 Dust ({stars_to_str(stars)})"
    gold = f"{coins} Coins"
    desc = f"{requester.mention}, you will receive:\n\n{gold}\n{dust}"
    return discord.Embed(title="Burn Card", description=desc, color=discord.Color.dark_grey())

def build_burn_result_embed(base: discord.Embed, text: str, color: discord.Color) -> discord.Embed:
    e = discord.Embed(title=base.title, description=base.description + f"\n\n{text}", color=color)
    return e

# ========= Upgrade embeds =========

def _upgrade_rule_for(stars: int):
    return UPGRADE_RULES.get(int(stars))

def build_upgrade_preview_embed(user: discord.abc.User, card: dict) -> discord.Embed:
    curr = int(card["stars"])
    rule = _upgrade_rule_for(curr)
    e = discord.Embed(title="Card Upgrade", color=discord.Color.orange())
    if rule is None:
        e.description = (
            "The upgrade succeeded! The card has been upgraded to **mint** condition.\n\n"
            f"{user.mention}, you have reached the highest condition for this card."
        )
        return e

    to = rule["to"]
    chance = int(round(rule["chance"] * 100))
    gold = rule["gold"]
    dust = rule["dust"]
    dust_label = f"- {dust} Dust ({stars_to_str(to)})"
    gold_label = f"- {gold} Gold"

    fail_text = "will not change" if rule["fail"] == "stay" else "will fall to **damaged**"
    e.description = (
        f"{user.mention}, upgrading the condition of `{card['card_uid']}` "
        f"from **{QUALITY_BY_STARS[curr]}** to **{QUALITY_BY_STARS[to]}** has a **{chance}%** chance of succeeding. "
        f"If this upgrade fails, the card's condition {fail_text}.\n\n"
        "Attempting the upgrade will cost the following resources:\n"
        f"-{dust_label}\n"
        f"-{gold_label}\n\n"
        "Use the 🔨 button to attempt the upgrade."
    )
    return e

def build_upgrade_outcome_embed(base: discord.Embed, success: bool, new_stars: int) -> discord.Embed:
    if success:
        text = f"The upgrade succeeded! The card has been upgraded to **{QUALITY_BY_STARS[new_stars]}** condition."
        return discord.Embed(title=base.title, description=text, color=discord.Color.green())
    else:
        text = f"The upgrade failed. The card is now **{QUALITY_BY_STARS[new_stars]}**."
        return discord.Embed(title=base.title, description=text, color=discord.Color.red())
