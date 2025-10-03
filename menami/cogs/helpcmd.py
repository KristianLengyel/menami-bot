from __future__ import annotations
import discord
from discord.ext import commands
from ..config import DROP_COOLDOWN_S, CLAIM_WINDOW_S

def build_help_embed() -> discord.Embed:
    e = discord.Embed(
        title="📖 MenamiBot Help",
        description=(
            f"Drop cooldown: `{DROP_COOLDOWN_S}s` • Claim window: `{CLAIM_WINDOW_S}s`\n"
            "React with **1️⃣ 2️⃣ 3️⃣** to claim a card."
        ),
        color=discord.Color.blurple(),
    )

    e.add_field(
        name="🎴 Drops & Claiming",
        value=(
            "`md` — Drop 3 cards\n"
            "React **1️⃣2️⃣3️⃣** to claim"
        ),
        inline=False,
    )

    e.add_field(
        name="💰 Economy",
        value=(
            "`mb` — Burn latest/UID\n"
            "Rewards: Coins + Dust by ★ (0–4)\n"
            "`mi` — Show inventory"
        ),
        inline=False,
    )

    e.add_field(
        name="🗂️ Collection",
        value=(
            "`mc` — Show collection\n"
            "Filters: `s:` series • `c:` char • `q:` stars\n"
            "`q>= / q<=` • `t:` tag (`none`=untagged)\n"
            "`e:` edition • `o:s` sort series"
        ),
        inline=False,
    )

    e.add_field(
        name="🏷️ Tags",
        value=(
            "`tags` — List\n"
            "`tc <name> <emoji>` — Create\n"
            "`td <name>` — Delete\n"
            "`t <tag> [uid]` — Tag a card\n"
            "`ut [uid]` — Remove tag"
        ),
        inline=False,
    )

    e.add_field(
        name="🔎 Cards",
        value=(
            "`mv` — View card (UID or latest)\n"
            "`ci` — Detailed card info\n"
            "Use **/give** to transfer a card"
        ),
        inline=False,
    )

    e.add_field(
        name="📊 Lookup",
        value=(
            "`mlu` — Character stats\n"
            "Format: `Series | Character`\n"
            "Shows totals, claim rate, editions"
        ),
        inline=False,
    )

    e.add_field(
        name="⚡ Quick Ref",
        value=(
            "`md mc mi mv ci mlu mb tags tc td t ut`"
        ),
        inline=False,
    )

    return e

class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="help", aliases=["mhelp"])
    async def cmd_help(self, ctx: commands.Context):
        await ctx.send(embed=build_help_embed())

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
