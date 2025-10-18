import discord
from discord.ext import commands
from menami.helpers import (
    generate_dye_code,
    random_color_hex_with_weights,
    dye_name_from_seed,
    emoji_shortcode_for_color,
)

class Dyes(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    @commands.command(name="dye")
    async def cmd_dye(self, ctx: commands.Context):
        code = generate_dye_code()
        color_hex = random_color_hex_with_weights()
        name = dye_name_from_seed(code, color_hex)
        charges = 1
        await self.db.create_user_dye(ctx.author.id, code, color_hex, charges, name)

        emoji = emoji_shortcode_for_color(color_hex)
        e = discord.Embed(
            title="New Dye Acquired",
            description=f"{emoji} `{code}` · {charges} charge · {name}\n{color_hex.upper()}",
            color=discord.Color.from_str(color_hex),
        )
        e.set_author(name=str(ctx.author), icon_url=getattr(ctx.author.display_avatar, "url", None))
        await ctx.reply(embed=e, mention_author=False)

    @commands.command(name="dyes")
    async def cmd_dyes(self, ctx: commands.Context):
        rows = await self.db.list_user_dyes(ctx.author.id)

        title = "Dye Collection"
        header = f"Dyes owned by {ctx.author.mention}"

        if not rows:
            e = discord.Embed(
                title=title,
                description=header + "\nNo dyes yet. Use `mu dye` to get one.",
                color=discord.Color.dark_grey(),
            )
            e.set_author(name=str(ctx.author), icon_url=getattr(ctx.author.display_avatar, "url", None))
            await ctx.reply(embed=e, mention_author=False)
            return

        lines = []
        for code, color_hex, charges, name in rows:
            emoji = emoji_shortcode_for_color(color_hex)
            charges_txt = "charge" if charges == 1 else "charges"
            lines.append(f"{emoji} `{code}` · {charges} {charges_txt} · {name}")

        e = discord.Embed(
            title=title,
            description=header + "\n\n" + "\n".join(lines),
            color=discord.Color.blurple(),
        )
        e.set_author(name=str(ctx.author), icon_url=getattr(ctx.author.display_avatar, "url", None))
        await ctx.reply(embed=e, mention_author=False)

    @commands.command(name="u")
    async def cmd_u(self, ctx: commands.Context, subcommand: str | None = None, *args):
        if not subcommand:
            await ctx.reply("Usage: `mu dye` or `mdyes`", mention_author=False)
            return
        sub = subcommand.lower()
        if sub == "dye":
            await self.cmd_dye(ctx)
        elif sub == "dyes":
            await self.cmd_dyes(ctx)
        else:
            await ctx.reply("Unknown subcommand. Try `mu dye` or `mdyes`.", mention_author=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(Dyes(bot))
