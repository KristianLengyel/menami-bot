import io
import random
import discord
from discord.ext import commands
from menami.helpers import (
    generate_dye_code,
    random_color_hex_with_weights,
    dye_name_from_seed,
    emoji_shortcode_for_color,
)
from menami.card_render import render_card_image, render_dye_preview

class Dyes(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    @commands.command(name="u")
    async def cmd_u(self, ctx: commands.Context, subcommand: str | None = None, *args):
        if not subcommand or subcommand.lower() != "dye":
            await ctx.reply("Usage: `mu dye` · get a new dye", mention_author=False)
            return

        code = generate_dye_code()
        color_hex = random_color_hex_with_weights()
        name = dye_name_from_seed(code, color_hex)
        charges = 1
        thickness = random.randint(5, 12)

        await self.db.create_user_dye(ctx.author.id, code, color_hex, charges, name, thickness)

        emoji = emoji_shortcode_for_color(color_hex)
        e = discord.Embed(
            title="New Dye Acquired",
            description=f"{emoji} `{code}` · {charges} charge · {name}\n"
                        f"{color_hex.upper()} · thickness **{thickness}**",
            color=discord.Color.from_str(color_hex),
        )
        e.set_author(name=str(ctx.author), icon_url=getattr(ctx.author.display_avatar, "url", None))
        await ctx.reply(embed=e, mention_author=False)

    @commands.command(name="dyes")
    async def cmd_mdyes(self, ctx: commands.Context):
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
        for code, color_hex, charges, name, thickness in rows:
            emoji = emoji_shortcode_for_color(color_hex)
            charges_txt = "charge" if charges == 1 else "charges"
            lines.append(f"{emoji} `{code}` · {charges} {charges_txt} · {name} · t={thickness}")

        e = discord.Embed(
            title=title,
            description=header + "\n\n" + "\n".join(lines),
            color=discord.Color.blurple(),
        )
        e.set_author(name=str(ctx.author), icon_url=getattr(ctx.author.display_avatar, "url", None))
        await ctx.reply(embed=e, mention_author=False)

    @commands.command(name="dye")
    async def cmd_mdye(self, ctx: commands.Context, a: str, b: str):
        uid = None
        code = None

        ca = await self.db.get_card(a)
        if ca:
            uid, code = a, b
        else:
            cb = await self.db.get_card(b)
            if cb:
                uid, code = b, a

        if uid is None:
            await ctx.reply("Card not found.", mention_author=False)
            return
        if not await self.db.user_owns_card(ctx.author.id, uid):
            await ctx.reply("You do not own this card.", mention_author=False)
            return

        dye = await self.db.get_user_dye(ctx.author.id, code)
        if not dye:
            await ctx.reply("Dye not found in your inventory.", mention_author=False)
            return

        _, color_hex, _, dye_name, thickness = dye

        card = await self.db.get_card(uid)
        url = await self.db.get_character_image(card["series"], card["character"], int(card["set_id"]))
        if not url:
            url = await self.db.get_character_image_any(card["series"], card["character"])

        before = await render_card_image(
            series=card["series"],
            character=card["character"],
            serial_number=int(card["serial_number"]),
            set_id=int(card["set_id"]),
            card_uid=card["card_uid"],
            image_url=url,
            fmt="PNG",
            apply_glow=False,
        )
        after = await render_card_image(
            series=card["series"],
            character=card["character"],
            serial_number=int(card["serial_number"]),
            set_id=int(card["set_id"]),
            card_uid=card["card_uid"],
            image_url=url,
            fmt="PNG",
            apply_glow=True,
            glow_color_hex=color_hex,
            glow_thickness=thickness,
        )
        preview = await render_dye_preview(before, after)

        class DyeView(discord.ui.View):
            def __init__(self, cog: "Dyes"):
                super().__init__(timeout=60)
                self.cog = cog
                self.result: bool | None = None

            @discord.ui.button(emoji="❌", style=discord.ButtonStyle.danger)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("Not your action.", ephemeral=True)
                    return
                self.result = False
                await interaction.response.defer()
                self.stop()

            @discord.ui.button(emoji="✅", style=discord.ButtonStyle.success)
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("Not your action.", ephemeral=True)
                    return
                ok = await self.cog.db.consume_user_dye(ctx.author.id, code)
                if not ok:
                    await interaction.response.send_message("You no longer have charges for that dye.", ephemeral=True)
                    return
                await self.cog.db.set_card_dye(uid, code, color_hex, dye_name, thickness)
                self.result = True
                await interaction.response.defer()
                self.stop()

        file = discord.File(io.BytesIO(preview), filename="preview.webp")
        e = discord.Embed(
            title="Dye Card",
            description=f"{ctx.author.mention}, apply **{dye_name}** (t={thickness}) to `{uid}`?",
            color=discord.Color.blurple(),
        )
        e.set_image(url="attachment://preview.webp")
        view = DyeView(self)
        msg = await ctx.reply(embed=e, file=file, view=view, mention_author=False)
        await view.wait()
        if view.result is None:
            te = discord.Embed(title="Dye Card", description="Timed out.", color=discord.Color.dark_grey())
            await msg.edit(embed=te, attachments=[], view=None)
            return
        if view.result is False:
            ce = discord.Embed(title="Dye Card", description="Canceled.", color=discord.Color.red())
            await msg.edit(embed=ce, attachments=[], view=None)
            return
        de = discord.Embed(title="Dye Card", description="The card has been dyed!", color=discord.Color.green())
        de.set_image(url="attachment://preview.webp")
        await msg.edit(embed=de, view=None)

async def setup(bot: commands.Bot):
    await bot.add_cog(Dyes(bot))
