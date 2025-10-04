# menami/cogs/wishlist.py
from __future__ import annotations
import math
import shlex
from typing import Optional

import discord
from discord.ext import commands

from ..config import WISHLIST_MAX

def _page_range_text(page: int, total: int, page_size: int, noun: str) -> str:
    if total == 0:
        return f"Showing {noun} 0–0 of 0"
    start = page * page_size + 1
    end = min((page + 1) * page_size, total)
    return f"Showing {noun} {start}–{end} of {total}"

def _parse_query(text: str) -> tuple[Optional[str], str]:
    if "|" in text:
        parts = [p.strip() for p in text.split("|", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            return parts[0], parts[1]
    return None, text.strip()

class WishlistCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="wishlist", aliases=["wl","mwl"])
    async def cmd_wishlist(self, ctx: commands.Context, member: Optional[discord.Member] = None, page: int = 0):
        target = member or ctx.author
        items = await self.bot.db.list_wishlist(target.id)
        total = len(items)

        page_size = 10
        pages = max(1, math.ceil(total / page_size))
        page = max(0, min(page, pages - 1))
        start = page * page_size
        end = start + page_size
        slice_ = items[start:end]

        lines = [f"{s} · {c}" for (s, c) in slice_] if slice_ else ["_No characters on wishlist._"]
        left = max(0, WISHLIST_MAX - total)

        desc = [
            f"Showing wishlist of {target.mention}",
            f"Available slots: {left}/{WISHLIST_MAX}",
            "",
            "\n".join(lines),
            "",
            _page_range_text(page, total, page_size, "characters")
        ]
        e = discord.Embed(title="Wishlist", description="\n".join(desc), color=discord.Color.blurple())
        await ctx.send(embed=e)

    @commands.command(name="wishadd", aliases=["wa","mwa"])
    async def cmd_wishadd(self, ctx: commands.Context, *, query: str):
        query = query.strip()
        if not query:
            return await ctx.send("Usage: `mwa Series | Character` or `mwa Character`")

        count = await self.bot.db.wishlist_count(ctx.author.id)
        if count >= WISHLIST_MAX:
            return await ctx.send(f"Your wishlist is full ({WISHLIST_MAX}). Remove an entry with `mwr` first.")

        series_raw, char_raw = _parse_query(query)
        to_add: list[tuple[str, str]] = []

        if series_raw:
            found = await self.bot.db.find_canonical_series_character(series_raw, char_raw)
            if not found:
                return await ctx.send("I couldn't find that series/character. Use `Series | Character` with exact names.")
            to_add = [found]
        else:
            matches = await self.bot.db.find_by_character_only(char_raw)
            if not matches:
                return await ctx.send("I couldn't find that character. Try `Series | Character`.")
            to_add = [matches[0]]
            if len(matches) > 1:
                alt = ", ".join(f"{s} · {c}" for s, c in matches[:5])
                await ctx.send(f"Note: multiple matches for `{char_raw}`. Added **{matches[0][0]} · {matches[0][1]}**.\n"
                               f"To pick a specific series next time, use: `mwa Series | {char_raw}`\n"
                               f"Examples: {alt}")

        added = 0
        for s, c in to_add:
            ok = await self.bot.db.add_wish(ctx.author.id, s, c)
            if ok:
                added += 1

        new_count = await self.bot.db.wishlist_count(ctx.author.id)
        left = max(0, WISHLIST_MAX - new_count)
        if added:
            return await ctx.send(f"✅ Added to wishlist. Slots left: {left}/{WISHLIST_MAX}")
        else:
            return await ctx.send("That entry already exists on your wishlist.")

    @commands.command(name="wishremove", aliases=["wr","mwr"])
    async def cmd_wishremove(self, ctx: commands.Context, *, query: str):
        query = query.strip()
        if not query:
            return await ctx.send("Usage: `mwr Series | Character` or `mwr Character` (removes all matches)")
        series_raw, char_raw = _parse_query(query)

        removed = await self.bot.db.remove_wish(ctx.author.id, series_raw, char_raw)
        if removed <= 0:
            return await ctx.send("No matching wishlist entry found.")
        else:
            count = await self.bot.db.wishlist_count(ctx.author.id)
            left = max(0, WISHLIST_MAX - count)
            spec = f"{series_raw} · {char_raw}" if series_raw else char_raw
            return await ctx.send(f"🗑️ Removed {removed} entr{'y' if removed==1 else 'ies'} for `{spec}`. Slots left: {left}/{WISHLIST_MAX}")

async def setup(bot: commands.Bot):
    await bot.add_cog(WishlistCog(bot))
