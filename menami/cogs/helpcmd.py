from __future__ import annotations
import discord
from discord.ext import commands
from ..config import (
    DROP_COOLDOWN_S,
    CLAIM_WINDOW_S,
    STAR_WEIGHTS,
    UPGRADE_RULES,
)

def _star_label(n: int) -> str:
    filled = "★" * n
    empty = "☆" * (4 - n)
    return filled + empty

def _drop_odds_line() -> str:
    total = float(sum(STAR_WEIGHTS)) if STAR_WEIGHTS else 0.0
    try:
        parts = []
        for i, w in enumerate(STAR_WEIGHTS):
            pct = (float(w) / total * 100.0) if total > 0 else 0.0
            parts.append(f"{_star_label(i)} ~{pct:.0f}%")
        return "Drop odds: " + " · ".join(parts)
    except Exception:
        return "Drop odds: evenly weighted (config error reading STAR_WEIGHTS)"

def _upgrade_rules_lines() -> list[str]:
    lines = []
    order = sorted(UPGRADE_RULES.keys())
    names = {0: "damaged", 1: "poor", 2: "good", 3: "excellent", 4: "mint"}
    for curr in order:
        r = UPGRADE_RULES[curr]
        to = r["to"]
        chance = int(round(float(r["chance"]) * 100))
        gold = int(r["gold"])
        dust = int(r["dust"])
        dust_stars = _star_label(to)
        fail_txt = "stay" if str(r.get("fail", "stay")) == "stay" else "damaged"
        lines.append(
            f"- {names[curr]} → {names[to]}: {chance}% • -{dust} Dust ({dust_stars}) • -{gold} Gold • fail: {fail_txt}"
        )
    lines.append("- mint: already max")
    return lines

def build_help_embed() -> discord.Embed:
    e = discord.Embed(
        title="📖 MenamiBot Help",
        description=(
            f"Drop cooldown: `{DROP_COOLDOWN_S}s` • Claim window: `{CLAIM_WINDOW_S}s`\n"
            "React with **1️⃣ 2️⃣ 3️⃣** to claim a card."
        ),
        color=discord.Color.blurple(),
    )

    # Drops section
    e.add_field(
        name="🎴 Drops & Claiming",
        value=(
            "`md` — Drop 3 cards\n"
            "React **1️⃣2️⃣3️⃣** to claim\n"
            f"{_drop_odds_line()}"
        ),
        inline=False,
    )

    # Economy
    e.add_field(
        name="💰 Economy",
        value=(
            "`mb` — Burn latest/UID (coins + 1 dust by ★)\n"
            "`mi` — Show inventory"
        ),
        inline=False,
    )

    # Upgrades
    e.add_field(
        name="🛠️ Upgrades",
        value=(
            "`mup` — Upgrade latest/UID (or use **/upgrade**)\n"
            "Press 🔨 to attempt (costs dust + gold)\n"
            + "\n".join(_upgrade_rules_lines())
        ),
        inline=False,
    )

    # Collection
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

    # Tags
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

    # Cards / transfer
    e.add_field(
        name="🔎 Cards",
        value=(
            "`mv` — View card (UID or latest)\n"
            "`ci` — Detailed card info\n"
            "Use **/give** to transfer a card"
        ),
        inline=False,
    )

    # Lookup
    e.add_field(
        name="📊 Lookup",
        value=(
            "`mlu` — Character stats\n"
            "Format: `Series | Character`\n"
            "Shows totals, claim rate, editions"
        ),
        inline=False,
    )

    # Quick ref
    e.add_field(
        name="⚡ Quick Ref",
        value=(
            "`md mc mi mv ci mlu mb mup tags tc td t ut`"
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
