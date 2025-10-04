from __future__ import annotations
import random
import time
import discord
from discord import app_commands
from discord.ext import commands

from ..config import (
    DROP_COOLDOWN_S,
    USER_DROP_COOLDOWN_S,
    GRAB_COOLDOWN_S,
    DAILY_COOLDOWN_S,
    DAILY_COINS_MIN, DAILY_COINS_MAX,
    DAILY_GEMS_MIN,  DAILY_GEMS_MAX,
)

def fmt_secs(n: int) -> str:
    if n <= 0:
        return "ready"
    h = n // 3600
    m = (n % 3600) // 60
    s = n % 60
    if h: return f"{h}h {m}m {s}s"
    if m: return f"{m}m {s}s"
    return f"{s}s"

class CooldownsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="cooldowns", description="Show your personal cooldowns (drop, grab, daily).")
    async def slash_cooldowns(self, interaction: discord.Interaction):
        embed = await self._build_embed(interaction.user, interaction.guild_id, interaction.channel_id)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="cooldowns", aliases=["cd", "mcd"])
    async def cmd_cooldowns(self, ctx: commands.Context):
        e = await self._build_embed(ctx.author, ctx.guild.id if ctx.guild else None, ctx.channel.id)
        await ctx.send(embed=e)

    async def _build_embed(self, user: discord.abc.User, guild_id: int | None, channel_id: int | None) -> discord.Embed:
        drop_left  = await self.bot.db.seconds_remaining(user.id, "drop", USER_DROP_COOLDOWN_S)
        grab_left  = await self.bot.db.seconds_remaining(user.id, "grab", GRAB_COOLDOWN_S)
        daily_left = await self.bot.db.seconds_remaining(user.id, "daily", DAILY_COOLDOWN_S)

        channel_left = None
        if guild_id and channel_id:
            cd = DROP_COOLDOWN_S
            try:
                v = await self.bot.db.get_drop_cooldown(guild_id)
                if v is not None:
                    cd = v
            except Exception:
                pass
            last = self.bot.channel_cooldowns.get(channel_id, 0)
            remain = int(max(0, cd - (time.time() - last)))
            if remain > 0:
                channel_left = remain

        desc = [
            f"**Drop**  · {fmt_secs(drop_left)}",
            f"**Grab**  · {fmt_secs(grab_left)}",
            f"**Daily** · {fmt_secs(daily_left)}",
        ]
        if channel_left is not None:
            desc.append(f"_Channel lock_ · {fmt_secs(channel_left)}")

        e = discord.Embed(title="Your Cooldowns", description="\n".join(desc), color=discord.Color.blurple())
        e.set_footer(text="Personal timers. Channel lock = server’s per-channel drop cooldown.")
        return e

    @app_commands.command(name="daily", description="Collect your daily reward (coins & gems).")
    async def slash_daily(self, interaction: discord.Interaction):
        e = await self._do_daily(interaction.user.id)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @commands.command(name="daily", aliases=["mdaily"])
    async def cmd_daily(self, ctx: commands.Context):
        e = await self._do_daily(ctx.author.id)
        await ctx.send(embed=e)

    async def _do_daily(self, user_id: int) -> discord.Embed:
        left = await self.bot.db.seconds_remaining(user_id, "daily", DAILY_COOLDOWN_S)
        if left > 0:
            return discord.Embed(
                title="Daily Reward",
                description=f"⏳ You already collected your daily. Come back in **{fmt_secs(left)}**.",
                color=discord.Color.orange(),
            )

        coins = random.randint(DAILY_COINS_MIN, DAILY_COINS_MAX)
        gems  = random.randint(DAILY_GEMS_MIN,  DAILY_GEMS_MAX)
        await self.bot.db.add_currency(user_id, coins=coins, gems=gems)
        await self.bot.db.set_timer(user_id, "daily")

        return discord.Embed(
            title="Daily Reward",
            description=f"🎉 You received **{coins} Coins** and **{gems} Gems**!",
            color=discord.Color.green(),
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(CooldownsCog(bot))
