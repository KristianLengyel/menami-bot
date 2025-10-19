import io
import asyncio
import math
import random
from collections import Counter
import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from menami.helpers import (
    generate_dye_code,
    random_color_hex_with_weights,
    dye_name_from_seed,
    emoji_shortcode_for_color,
)
from menami.card_render import render_card_image, render_dye_preview, render_dye_token

DYE_BASE_PATH = "assets/dyes/dye_base.png"

class Dyes(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    @commands.command(name="u")
    async def cmd_u(self, ctx: commands.Context, subcommand: str | None = None, *args):
        if subcommand is None:
            subcommand = "dye"

        if subcommand.lower() == "dye":
            code = generate_dye_code()
            color_hex = random_color_hex_with_weights()
            name = dye_name_from_seed(code, color_hex)
            charges = 1
            thickness = random.randint(5, 12)
            await self.db.create_user_dye(ctx.author.id, code, color_hex, charges, name, thickness)
            emoji = emoji_shortcode_for_color(color_hex)

            e = discord.Embed(
                title="Dye Obtained",
                description=(
                    f"**{name}**\n"
                    f"Owner: {ctx.author.mention}\n"
                    f"Code: `{code}`\n"
                    f"Color: `{color_hex.upper()}`\n"
                    f"Glow: **{thickness}**\n"
                    f"Charges: **{charges}**"
                ),
                color=discord.Color.from_str(color_hex),
            )

            icon_bytes = await asyncio.to_thread(render_dye_token, color_hex, thickness, DYE_BASE_PATH, "PNG")
            icon_file = discord.File(io.BytesIO(icon_bytes), filename="dye.png")
            e.set_thumbnail(url="attachment://dye.png")

            await ctx.reply(embed=e, file=icon_file, mention_author=False)
            return

        if subcommand.lower() == "auto_dye":
            if not await self.bot.is_owner(ctx.author):
                await ctx.reply("Only the bot owner can use `mu auto_dye`.", mention_author=False)
                return

            times = 500
            delay = 1.0
            silent = True
            if len(args) >= 1:
                try:
                    times = max(1, min(int(args[0]), 5000))
                except:
                    pass
            if len(args) >= 2:
                try:
                    delay = max(0.1, float(args[1]))
                except:
                    pass
            if len(args) >= 3:
                silent = str(args[2]).lower() in ("1", "true", "t", "yes", "y")

            if not silent:
                await ctx.reply(f"Starting {times} × `mu dye` (every {delay:.2f}s)...", mention_author=False)
                for i in range(times):
                    try:
                        await self.cmd_u.callback(self, ctx, "dye")
                    except Exception as e:
                        await ctx.send(f"Error on run {i+1}: {e}")
                    await asyncio.sleep(delay)
                await ctx.send(f"✅ Done. Generated {times} dyes.")
                return

            await ctx.reply(f"Starting silent generation: {times} dyes (every {delay:.2f}s)...", mention_author=False)
            counts = Counter()
            failures = 0
            for i in range(times):
                try:
                    code = generate_dye_code()
                    color_hex = random_color_hex_with_weights()
                    name = dye_name_from_seed(code, color_hex)
                    charges = 1
                    thickness = random.randint(5, 12)
                    await self.db.create_user_dye(ctx.author.id, code, color_hex, charges, name, thickness)
                    counts[emoji_shortcode_for_color(color_hex)] += 1
                except Exception as e:
                    failures += 1
                    if (i % 25) == 0:
                        await ctx.send(f"Error at {i+1}: {e}")
                await asyncio.sleep(delay)
                if (i + 1) % 50 == 0:
                    top = ", ".join(f"{k}×{v}" for k, v in counts.most_common(6))
                    await ctx.send(f"Progress {i+1}/{times}… {top}")
            total = sum(counts.values())
            top = ", ".join(f"{k}×{v}" for k, v in counts.most_common(10)) or "—"
            e = discord.Embed(
                title="Auto Dye (silent) — Summary",
                description=(
                    f"User: {ctx.author.mention}\n"
                    f"Generated: **{total}** dyes\n"
                    f"Failures: **{failures}**\n\n"
                    f"Top buckets: {top}"
                ),
                color=discord.Color.green(),
            )
            e.set_author(name=str(ctx.author), icon_url=getattr(ctx.author.display_avatar, "url", None))
            await ctx.send(embed=e)
            return

        await ctx.reply("Usage:\n`mu dye`\n`mu auto_dye <times> <delay> <silent>`", mention_author=False)

    @cmd_u.error
    async def cmd_u_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.NotOwner):
            await ctx.reply("Only the bot owner can run that.", mention_author=False, delete_after=6)
        else:
            raise error

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
        page_size = 10
        total_pages = max(1, math.ceil(len(rows) / page_size))
        def page_embed(page: int) -> discord.Embed:
            start = page * page_size
            end = start + page_size
            subset = rows[start:end]
            lines = []
            for code, color_hex, charges, name, thickness in subset:
                emoji = emoji_shortcode_for_color(color_hex)
                charges_txt = "charge" if charges == 1 else "charges"
                lines.append(f"{emoji} `{code}` · {charges} {charges_txt} · {name} · t={thickness}")
            desc = header + "\n\n" + ("\n".join(lines) if lines else "_No dyes on this page._")
            e = discord.Embed(title=title, description=desc, color=discord.Color.blurple())
            e.set_author(name=str(ctx.author), icon_url=getattr(ctx.author.display_avatar, "url", None))
            e.set_footer(text=f"Page {page + 1}/{total_pages} • {len(rows)} total")
            return e
        class DyesPager(discord.ui.View):
            def __init__(self, author_id: int):
                super().__init__(timeout=120)
                self.author_id = author_id
                self.page = 0
                self.msg: discord.Message | None = None
                self.update_buttons()
            def update_buttons(self):
                for child in self.children:
                    if isinstance(child, discord.ui.Button):
                        if child.custom_id == "first":
                            child.disabled = self.page <= 0
                        elif child.custom_id == "prev":
                            child.disabled = self.page <= 0
                        elif child.custom_id == "next":
                            child.disabled = self.page >= total_pages - 1
                        elif child.custom_id == "last":
                            child.disabled = self.page >= total_pages - 1
            async def interaction_guard(self, interaction: discord.Interaction) -> bool:
                if interaction.user.id != self.author_id:
                    await interaction.response.send_message("Not your list.", ephemeral=True)
                    return False
                return True
            @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, custom_id="first")
            async def first_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
                if not await self.interaction_guard(interaction):
                    return
                self.page = 0
                self.update_buttons()
                await interaction.response.edit_message(embed=page_embed(self.page), view=self)
            @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary, custom_id="prev")
            async def prev_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
                if not await self.interaction_guard(interaction):
                    return
                if self.page > 0:
                    self.page -= 1
                self.update_buttons()
                await interaction.response.edit_message(embed=page_embed(self.page), view=self)
            @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary, custom_id="next")
            async def next_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
                if not await self.interaction_guard(interaction):
                    return
                if self.page < total_pages - 1:
                    self.page += 1
                self.update_buttons()
                await interaction.response.edit_message(embed=page_embed(self.page), view=self)
            @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="last")
            async def last_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
                if not await self.interaction_guard(interaction):
                    return
                self.page = total_pages - 1
                self.update_buttons()
                await interaction.response.edit_message(embed=page_embed(self.page), view=self)
            async def on_timeout(self):
                try:
                    if self.msg:
                        await self.msg.edit(view=None)
                except Exception:
                    pass
        view = DyesPager(ctx.author.id)
        embed = page_embed(0)
        msg = await ctx.reply(embed=embed, view=view, mention_author=False)
        view.msg = msg

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

    @commands.command(name="dyes_gallery", aliases=["dg"])
    async def cmd_dyes_gallery(self, ctx: commands.Context, sort: str | None = None):
        rows = await self.db.list_user_dyes(ctx.author.id)
        if not rows:
            e = discord.Embed(
                title="Dye Gallery",
                description=f"{ctx.author.mention}\nNo dyes yet. Use `mu dye` to get one.",
                color=discord.Color.dark_grey(),
            )
            e.set_author(name=str(ctx.author), icon_url=getattr(ctx.author.display_avatar, "url", None))
            await ctx.reply(embed=e, mention_author=False)
            return

        def _hue_of_hex(hx: str) -> float:
            r = int(hx[1:3], 16) / 255.0
            g = int(hx[3:5], 16) / 255.0
            b = int(hx[5:7], 16) / 255.0
            import colorsys
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            return h

        s = (sort or "hue").lower().strip()
        if s == "oldest":
            rows_sorted = list(reversed(rows))
        elif s == "charges":
            rows_sorted = sorted(rows, key=lambda r: (-int(r[2]), r[0]))
        elif s == "thickness":
            rows_sorted = sorted(rows, key=lambda r: (-int(r[4]), r[0]))
        elif s == "newest":
            rows_sorted = rows
        else:
            rows_sorted = sorted(rows, key=lambda r: (_hue_of_hex(r[1]), -int(r[2])))

        per_row = 8
        tile_size = 128 if len(rows_sorted) < 200 else 104
        page_items = 56 if tile_size <= 112 else 48
        total_pages = max(1, math.ceil(len(rows_sorted) / page_items))

        async def render_sheet(page: int) -> tuple[discord.Embed, discord.File]:
            start = page * page_items
            end = start + page_items
            subset = rows_sorted[start:end]
            pad = 16
            cols = per_row
            rows_cnt = max(1, math.ceil(len(subset) / cols))
            w = pad + cols * (tile_size + pad)
            h = pad + rows_cnt * (tile_size + 36 + pad)
            canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))

            try:
                f_code = ImageFont.truetype("arial.ttf", 16)
            except Exception:
                f_code = ImageFont.load_default()

            x = pad
            y = pad
            for i, (code, color_hex, charges, name, thickness) in enumerate(subset):
                token_bytes = await asyncio.to_thread(render_dye_token, color_hex, thickness, DYE_BASE_PATH, "PNG")
                im = Image.open(io.BytesIO(token_bytes)).convert("RGBA").resize((tile_size, tile_size))
                canvas.alpha_composite(im, (x, y))

                d = ImageDraw.Draw(canvas)
                badge_r = 10
                cx = x + tile_size - badge_r - 8
                cy = y + 8 + badge_r
                if int(charges) > 0:
                    d.ellipse((cx - badge_r, cy - badge_r, cx + badge_r, cy + badge_r), fill=(255, 255, 255, 230), outline=(0, 0, 0, 220), width=2)
                else:
                    d.ellipse((cx - badge_r, cy - badge_r, cx + badge_r, cy + badge_r), fill=None, outline=(255, 255, 255, 230), width=2)

                tw, th = d.textbbox((0, 0), code, font=f_code)[2:]
                tx = x + (tile_size - tw) // 2
                ty = y + tile_size + 6
                d.rounded_rectangle((x + 4, ty - 4, x + tile_size - 4, ty + th + 4), 6, fill=(0, 0, 0, 150))
                d.text((tx, ty), code, font=f_code, fill=(255, 255, 255, 240))

                x += tile_size + pad
                if (i + 1) % cols == 0:
                    x = pad
                    y += tile_size + 36 + pad

            out = io.BytesIO()
            canvas.save(out, format="WEBP")
            file = discord.File(io.BytesIO(out.getvalue()), filename="dyes.webp")

            e = discord.Embed(
                title="Dye Gallery",
                description=f"{ctx.author.mention} • {len(rows_sorted)} dyes • Page {page + 1}/{total_pages}",
                color=discord.Color.blurple(),
            )
            e.set_author(name=str(ctx.author), icon_url=getattr(ctx.author.display_avatar, "url", None))
            e.set_image(url="attachment://dyes.webp")
            return e, file

        class GalleryPager(discord.ui.View):
            def __init__(self, author_id: int):
                super().__init__(timeout=180)
                self.author_id = author_id
                self.page = 0
                self.msg: discord.Message | None = None

            async def refresh(self, interaction: discord.Interaction):
                embed, file = await render_sheet(self.page)
                await interaction.response.edit_message(embed=embed, attachments=[file], view=self)

            async def interaction_guard(self, interaction: discord.Interaction) -> bool:
                if interaction.user.id != self.author_id:
                    await interaction.response.send_message("Not your gallery.", ephemeral=True)
                    return False
                return True

            @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary)
            async def first_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
                if not await self.interaction_guard(interaction):
                    return
                self.page = 0
                await self.refresh(interaction)

            @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
            async def prev_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
                if not await self.interaction_guard(interaction):
                    return
                if self.page > 0:
                    self.page -= 1
                await self.refresh(interaction)

            @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
            async def next_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
                if not await self.interaction_guard(interaction):
                    return
                if self.page < total_pages - 1:
                    self.page += 1
                await self.refresh(interaction)

            @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
            async def last_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
                if not await self.interaction_guard(interaction):
                    return
                self.page = total_pages - 1
                await self.refresh(interaction)

            async def on_timeout(self):
                try:
                    if self.msg:
                        await self.msg.edit(view=None)
                except Exception:
                    pass

        view = GalleryPager(ctx.author.id)
        embed, file = await render_sheet(0)
        sent = await ctx.reply(embed=embed, file=file, view=view, mention_author=False)
        view.msg = sent

async def setup(bot: commands.Bot):
    await bot.add_cog(Dyes(bot))