from __future__ import annotations
import shlex
from typing import List, Tuple
import discord
from discord import app_commands
from discord.ext import commands
import io

from ..card_render import render_card_image

from ..embeds import (
    format_card_embed,
    build_simple_cardinfo_embed,
    build_character_lookup_embed,
    build_burn_preview_embed,
    build_upgrade_preview_embed,
)
from ..views import (
    InventoryView,
    CollectionView,
    ConfirmBurnView,
    balances_to_items,
    UpgradeView,
    EditionLookupView,
)

async def _render_attachment(bot, card):
    try:
        url = await bot.db.get_character_image(card["series"], card["character"], int(card["set_id"])) \
              or await bot.db.get_character_image_any(card["series"], card["character"])
        if not url:
            return None

        img_bytes = await render_card_image(
            series=card["series"],
            character=card["character"],
            serial_number=int(card["serial_number"]),
            set_id=int(card["set_id"]),
            card_uid=card["card_uid"],
            image_url=url,
            fmt="PNG",
        )
        fname = f"{card['card_uid']}.png"
        return discord.File(io.BytesIO(img_bytes), filename=fname), fname
    except Exception:
        return None

def parse_collection_filters(text: str) -> dict:
    f: dict = {}
    if not text:
        return f

    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = text.split()

    for raw in tokens:
        arg = raw.strip()
        if not arg:
            continue

        low = arg.lower()

        if low.startswith("s:"):
            f["s"] = arg[2:].strip(); continue

        if low.startswith("c:"):
            f["c"] = arg[2:].strip(); continue

        if low.startswith("q>="):
            try:
                f["q_op"] = ">="; f["q_val"] = int(arg[3:])
            except ValueError: pass
            continue

        if low.startswith("q<="):
            try:
                f["q_op"] = "<="; f["q_val"] = int(arg[3:])
            except ValueError: pass
            continue

        if low.startswith("q:"):
            try:
                f["q"] = int(arg[2:])
            except ValueError: pass
            continue

        if low.startswith("o:"):
            val = low[2:]
            f["o"] = "s" if val in ("s", "series") else "d"
            continue

        if low.startswith("t:"):
            val = arg[2:].strip()
            f["t"] = "none" if val.lower() == "none" else val
            continue

        if low.startswith("e:"):
            try:
                f["e"] = int(arg[2:])
            except ValueError: pass
            continue

    return f

class InventoryCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -------- Collection --------
    @app_commands.command(name="collection", description="Show a user's collection.")
    @app_commands.describe(user="User to view, defaults to you")
    async def slash_collection(self, interaction: discord.Interaction, user: discord.User | None = None):
        target = user or interaction.user
        rows = await self.bot.db.inventory(target.id)
        if not rows:
            return await interaction.response.send_message(f"{target.mention} has no cards yet.", ephemeral=True)
        view = CollectionView(self.bot, target, rows, ephemeral=True)
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=False)

    @commands.command(name="c", aliases=["mc"])
    async def cmd_collection(self, ctx: commands.Context, *, filters_text: str | None = None):
        target = ctx.author
        if not filters_text or not filters_text.strip():
            rows = await self.bot.db.inventory(target.id)
        else:
            flt = parse_collection_filters(filters_text)
            rows = await self.bot.db.inventory_filtered(target.id, flt)

        if not rows:
            msg = f"{target.mention} has no cards yet." if not filters_text else f"{target.mention} has no cards matching filters."
            return await ctx.send(msg)

        view = CollectionView(self.bot, target, rows)
        await ctx.send(embed=view.build_embed(), view=view)

    @commands.command(name="imgset", aliases=["mimgset"])
    @commands.has_permissions(manage_guild=True)
    async def cmd_imgset(self, ctx, edition: int, *, query: str):
        parts = [p.strip() for p in query.split("|")]
        if len(parts) != 2:
            return await ctx.send("Format: `mimgset <edition> Series | Character`")

        series, character = parts
        url = None
        size = None
        mime = None

        if ctx.message.attachments:
            a = ctx.message.attachments[0]
            url = a.url
            size = a.size
            mime = a.content_type

        if not url:
            return await ctx.send("Please attach an image (520x700px, ~100–140KB).")

        if size and size > 200_000:
            return await ctx.send("⚠️ Keep images ≤ 200KB.")

        await self.bot.db.set_character_image(series, character, int(edition), url, size, mime)
        await ctx.send(f"✅ Image set for {character} · {series} · ◈{edition}")

    # -------- Inventory --------
    @app_commands.command(name="inventory", description="Show your items (coin, gem, ticket) with pagination.")
    @app_commands.describe(user="User to view, defaults to you")
    async def slash_inventory(self, interaction: discord.Interaction, user: discord.User | None = None):
        target = user or interaction.user
        bal = await self.bot.db.get_items(target.id)
        items_all = balances_to_items(bal)
        view = InventoryView(self.bot, target, items_all, ephemeral=True)
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=False)

    @commands.command(name="i", aliases=["mi"])
    async def cmd_inventory_items(self, ctx: commands.Context, member: discord.Member | None = None):
        target = member or ctx.author
        bal = await self.bot.db.get_items(target.id)
        items_all = balances_to_items(bal)
        view = InventoryView(self.bot, target, items_all)
        await ctx.send(embed=view.build_embed(), view=view)

    # -------- View / Give --------
    @app_commands.command(name="view", description="View a card by its ID.")
    @app_commands.describe(card_id="Card UID (leave empty for latest)")
    async def slash_view(self, interaction: discord.Interaction, card_id: str | None = None):
        if card_id:
            card = await self.bot.db.get_card(card_id.strip())
        else:
            card = await self.bot.db.get_latest_card(interaction.user.id)
        if not card:
            return await interaction.response.send_message("Card not found.", ephemeral=True)

        embed = format_card_embed(card, claimed=card["grabbed_by"] is not None)

        try:
            attach = await _render_attachment(self.bot, card)
        except Exception:
            attach = None

        if attach:
            file, fname = attach
            embed.set_image(url=f"attachment://{fname}")
            await interaction.response.send_message(embed=embed, file=file)
        else:
            await interaction.response.send_message(embed=embed)

    # -------- Burn --------
    @app_commands.command(name="burn", description="Burn a card for coins and dust (with confirmation).")
    @app_commands.describe(card_id="Card UID (leave empty for latest)")
    async def slash_burn(self, interaction: discord.Interaction, card_id: str | None = None):
        if card_id:
            card = await self.bot.db.get_card(card_id.strip())
        else:
            card = await self.bot.db.get_latest_card(interaction.user.id)

        if not card:
            return await interaction.response.send_message("Card not found.", ephemeral=True)
        if card.get("owned_by") != str(interaction.user.id):
            return await interaction.response.send_message("You don't own that card.", ephemeral=True)

        stars = int(card["stars"])
        embed = build_burn_preview_embed(interaction.user, stars)
        view = ConfirmBurnView(self.bot, interaction.user.id, card["card_uid"], stars)
        await interaction.response.send_message(embed=embed, view=view)
        sent = await interaction.original_response()
        view.message = sent

    @commands.command(name="b", aliases=["mb"])
    async def cmd_burn(self, ctx: commands.Context, card_id: str | None = None):
        if card_id:
            card = await self.bot.db.get_card(card_id.strip())
        else:
            card = await self.bot.db.get_latest_card(ctx.author.id)

        if not card:
            return await ctx.send("Card not found.")
        if card.get("owned_by") != str(ctx.author.id):
            return await ctx.send("You don't own that card.")

        stars = int(card["stars"])
        embed = build_burn_preview_embed(ctx.author, stars)
        view = ConfirmBurnView(self.bot, ctx.author.id, card["card_uid"], stars)
        sent = await ctx.send(embed=embed, view=view)
        view.message = sent

    # -------- Upgrade --------
    @app_commands.command(name="upgrade", description="Preview and attempt an upgrade for a card.")
    @app_commands.describe(card_id="Card UID (leave empty for latest)")
    async def slash_upgrade(self, interaction: discord.Interaction, card_id: str | None = None):
        if card_id:
            card = await self.bot.db.get_card(card_id.strip())
        else:
            card = await self.bot.db.get_latest_card(interaction.user.id)

        if not card:
            return await interaction.response.send_message("Card not found.", ephemeral=True)
        if card.get("owned_by") != str(interaction.user.id):
            return await interaction.response.send_message("You don't own that card.", ephemeral=True)

        preview = build_upgrade_preview_embed(interaction.user, card)
        view = UpgradeView(self.bot, interaction.user.id, card["card_uid"])
        await interaction.response.send_message(embed=preview, view=view)
        sent = await interaction.original_response()
        view.message = sent

    @commands.command(name="upgrade", aliases=["mup", "up"])
    async def cmd_upgrade(self, ctx: commands.Context, card_id: str | None = None):
        if card_id:
            card = await self.bot.db.get_card(card_id.strip())
        else:
            card = await self.bot.db.get_latest_card(ctx.author.id)

        if not card:
            return await ctx.send("Card not found.")
        if card.get("owned_by") != str(ctx.author.id):
            return await ctx.send("You don't own that card.")

        preview = build_upgrade_preview_embed(ctx.author, card)
        view = UpgradeView(self.bot, ctx.author.id, card["card_uid"])
        sent = await ctx.send(embed=preview, view=view)
        view.message = sent

    # -------- Misc view helpers --------
    @commands.command(name="view", aliases=["mv", "v"])
    async def cmd_view(self, ctx: commands.Context, card_id: str | None = None):
        if card_id:
            card = await self.bot.db.get_card(card_id.strip())
        else:
            card = await self.bot.db.get_latest_card(ctx.author.id)

        if not card:
            return await ctx.send("Card not found.")

        embed = build_simple_cardinfo_embed(card)
        attach = await _render_attachment(self.bot, card)
        if attach:
            file, fname = attach
            embed.set_image(url=f"attachment://{fname}")
            await ctx.send(embed=embed, file=file)
        else:
            await ctx.send(embed=embed)

    @commands.command(name="cardinfo", aliases=["ci"])
    async def cmd_cardinfo(self, ctx: commands.Context, card_id: str | None = None):
        if card_id:
            card = await self.bot.db.get_card(card_id.strip())
        else:
            card = await self.bot.db.get_latest_card(ctx.author.id)

        if not card:
            return await ctx.send("Card not found.")

        embed = format_card_embed(card, claimed=card["grabbed_by"] is not None)
        await ctx.send(embed=embed)

    # -------- Lookup & Tags (unchanged) --------
    @commands.command(name="lookup", aliases=["mlu", "lu"])
    async def cmd_lookup(self, ctx: commands.Context, *, query: str | None = None):
        if not query:
            latest = await self.bot.db.get_latest_card(ctx.author.id)
            if not latest:
                return await ctx.send("You don't own any cards yet.")
            series = latest["series"]
            character = latest["character"]
            current_set = int(latest["set_id"])

            stats_all = await self.bot.db.character_stats(series, character, set_id=None)
            editions = stats_all["editions"]
            if editions:
                try:
                    start_index = editions.index(current_set)
                except ValueError:
                    start_index = 0
                view = EditionLookupView(
                    self.bot, series, character, editions,
                    start_index=start_index, requester_id=ctx.author.id
                )
                embed = await view.build_embed()
                sent = await ctx.send(embed=embed, view=view)
                view.message = sent
            else:
                stats = stats_all
                embed = build_character_lookup_embed(stats, edition_index=1)
                await ctx.send(embed=embed)
            return

        parts = [p.strip() for p in query.split("|")]
        if len(parts) != 2:
            return await ctx.send("Format: `Series | Character` (or just `mlu` for your latest card)")

        series, character = parts
        stats_all = await self.bot.db.character_stats(series, character, set_id=None)
        editions = stats_all["editions"]
        if editions:
            view = EditionLookupView(self.bot, series, character, editions, start_index=0)
            embed = await view.build_embed()
            sent = await ctx.send(embed=embed, view=view)
            view.message = sent
        else:
            stats = stats_all
            embed = build_character_lookup_embed(stats, edition_index=1)
            await ctx.send(embed=embed)

    @commands.command(name="tags")
    async def cmd_tags(self, ctx: commands.Context):
        tags = await self.bot.db.list_tags(ctx.author.id)
        if not tags:
            return await ctx.send("You have no tags yet. Create one with `tc <name> <emoji>`.")
        lines = [f"{t['emoji']} `{t['name']}`" for t in tags]
        await ctx.send("**Your Tags:**\n" + "\n".join(lines))

    @commands.command(name="tagcreate", aliases=["tc"])
    async def cmd_tagcreate(self, ctx: commands.Context, name: str, emoji: str):
        ok = await self.bot.db.create_tag(ctx.author.id, name, emoji)
        if not ok:
            return await ctx.send(f"⚠️ Tag `{name}` already exists.")
        await ctx.send(f"✅ Created tag `{name}` with {emoji}")

    @commands.command(name="tagdelete", aliases=["td"])
    async def cmd_tagdelete(self, ctx: commands.Context, name: str):
        ok = await self.bot.db.delete_tag(ctx.author.id, name)
        if not ok:
            return await ctx.send(f"⚠️ Tag `{name}` not found.")
        await ctx.send(f"🗑️ Deleted tag `{name}`")

    @commands.command(name="tag", aliases=["t"])
    async def cmd_tag(self, ctx: commands.Context, tag_name: str, card_uid: str | None = None):
        if not card_uid:
            latest = await self.bot.db.get_latest_card(ctx.author.id)
            if not latest:
                return await ctx.send("You don't own any cards yet.")
            card_uid = latest["card_uid"]

        card = await self.bot.db.get_card(card_uid.strip())
        if not card:
            return await ctx.send("Card not found.")
        if card["owned_by"] != str(ctx.author.id):
            return await ctx.send("You don’t own this card.")

        ok = await self.bot.db.assign_tag(ctx.author.id, card_uid.strip(), tag_name)
        if not ok:
            return await ctx.send(f"⚠️ Tag `{tag_name}` not found. Use `tc <name> <emoji>` first.")
        await ctx.send(f"✅ Tagged card `{card_uid}` with `{tag_name}`")

    @commands.command(name="untag", aliases=["ut"])
    async def cmd_untag(self, ctx: commands.Context, card_uid: str | None = None):
        if not card_uid:
            latest = await self.bot.db.get_latest_card(ctx.author.id)
            if not latest:
                return await ctx.send("You don't own any cards yet.")
            card_uid = latest["card_uid"]

        card = await self.bot.db.get_card(card_uid.strip())
        if not card:
            return await ctx.send("Card not found.")
        if card["owned_by"] != str(ctx.author.id):
            return await ctx.send("You don’t own this card.")

        await self.bot.db.untag_card(card_uid.strip())
        await ctx.send(f"✅ Removed tag from `{card_uid}`")

async def setup(bot: commands.Bot):
    await bot.add_cog(InventoryCog(bot))
