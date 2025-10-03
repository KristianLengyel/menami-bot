from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands

class SettingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="mset", description="Set the active channel where cards can drop. Omit to use current channel.")
    @app_commands.describe(channel="Channel to allow drops in")
    async def slash_mset(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None):
        if not interaction.user.guild_permissions.manage_guild and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("You need Manage Server permission.", ephemeral=True)
        ch = channel or interaction.channel
        if not isinstance(ch, discord.TextChannel):
            return await interaction.response.send_message("Pick a text channel.", ephemeral=True)
        await self.bot.db.set_drop_channel(interaction.guild_id, ch.id)
        await interaction.response.send_message(f"Active drop channel set to {ch.mention}.")

    @commands.command(name="set", aliases=["mset"])
    async def cmd_mset(self, ctx: commands.Context, channel: discord.TextChannel | None = None):
        if not ctx.author.guild_permissions.manage_guild and not ctx.author.guild_permissions.administrator:
            return await ctx.send("You need Manage Server permission.")
        ch = channel or ctx.channel
        if not isinstance(ch, discord.TextChannel):
            return await ctx.send("Pick a text channel.")
        await self.bot.db.set_drop_channel(ctx.guild.id, ch.id)
        await ctx.send(f"Active drop channel set to {ch.mention}.")

    @app_commands.command(name="cooldown", description="Set or reset the drop cooldown for this server.")
    @app_commands.describe(seconds="Cooldown in seconds (5–3600). Omit to view, 0 to reset to default.")
    async def slash_cooldown(self, interaction: discord.Interaction, seconds: int | None = None):
        if not interaction.user.guild_permissions.manage_guild and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("You need Manage Server permission.", ephemeral=True)
        if seconds is None:
            cur = await self.bot.db.get_drop_cooldown(interaction.guild_id)
            return await interaction.response.send_message(f"Current drop cooldown: {cur if cur is not None else 'default'}s", ephemeral=True)
        if seconds == 0:
            await self.bot.db.set_drop_cooldown(interaction.guild_id, None)
            return await interaction.response.send_message("Drop cooldown reset to default.")
        if seconds < 5 or seconds > 3600:
            return await interaction.response.send_message("Cooldown must be between 5 and 3600 seconds.", ephemeral=True)
        await self.bot.db.set_drop_cooldown(interaction.guild_id, seconds)
        await interaction.response.send_message(f"Drop cooldown set to {seconds}s.")

    @commands.command(name="cooldown", aliases=["cd"])
    async def cmd_cooldown(self, ctx: commands.Context, seconds: int | None = None):
        if not ctx.author.guild_permissions.manage_guild and not ctx.author.guild_permissions.administrator:
            return await ctx.send("You need Manage Server permission.")
        if seconds is None:
            cur = await self.bot.db.get_drop_cooldown(ctx.guild.id)
            return await ctx.send(f"Current drop cooldown: {cur if cur is not None else 'default'}s")
        if seconds == 0:
            await self.bot.db.set_drop_cooldown(ctx.guild.id, None)
            return await ctx.send("Drop cooldown reset to default.")
        if seconds < 5 or seconds > 3600:
            return await ctx.send("Cooldown must be between 5 and 3600 seconds.")
        await self.bot.db.set_drop_cooldown(ctx.guild.id, seconds)
        await ctx.send(f"Drop cooldown set to {seconds}s.")

async def setup(bot: commands.Bot):
    await bot.add_cog(SettingsCog(bot))
