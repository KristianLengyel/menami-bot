from __future__ import annotations
from typing import List, Tuple
import math
import discord
import shlex
from discord import app_commands
from discord.ext import commands

from ..utils import stars_to_str, format_card_embed

def page_range_text(page: int, total: int, page_size: int, noun: str) -> str:
    if total == 0:
        return f"Showing {noun} 0–0 of 0"
    start = page * page_size + 1
    end = min((page + 1) * page_size, total)
    return f"Showing {noun} {start}–{end} of {total}"

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
            f["s"] = arg[2:].strip()
            continue

        if low.startswith("c:"):
            f["c"] = arg[2:].strip()
            continue

        if low.startswith("q>="):
            try:
                f["q_op"] = ">="
                f["q_val"] = int(arg[3:])
            except ValueError:
                pass
            continue

        if low.startswith("q<="):
            try:
                f["q_op"] = "<="
                f["q_val"] = int(arg[3:])
            except ValueError:
                pass
            continue

        if low.startswith("q:"):
            try:
                f["q"] = int(arg[2:])
            except ValueError:
                pass
            continue

        if low.startswith("o:"):
            val = low[2:]
            if val in ("s", "series"):
                f["o"] = "s"
            else:
                f["o"] = "d"
            continue

        if low.startswith("t:"):
            val = arg[2:].strip()
            f["t"] = "none" if val.lower() == "none" else val
            continue

        if low.startswith("e:"):
            try:
                f["e"] = int(arg[2:])
            except ValueError:
                pass
            continue

    return f

def slice_page(items: List[str], page: int, page_size: int) -> List[str]:
    start = page * page_size
    end = start + page_size
    return items[start:end]

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
    e.set_footer(text=f"Showing edition {edition_index} of {total_editions}")
    return e

PAGE_SIZE_ITEMS = 10

def get_other_items_for_user(user_id: int) -> List[str]:
    return []

def balances_to_items(bal: dict) -> List[str]:
    base = [
        f":coin: **{bal['coins']:,}** · `coin` · *Coin*",
        f":gem: **{bal['gems']:,}** · `gem` · *Gem*",
        f":tickets: **{bal['tickets']:,}** · `ticket` · *Ticket*",
    ]
    dust_specs = [
        ("✨", bal.get("dust_mint", 0), "dust_mint", "mint", 4),
        ("✨", bal.get("dust_excellent", 0), "dust_excellent", "excellent", 3),
        ("✨", bal.get("dust_good", 0), "dust_good", "good", 2),
        ("✨", bal.get("dust_poor", 0), "dust_poor", "poor", 1),
        ("✨", bal.get("dust_damaged", 0), "dust_damaged", "damaged", 0),
    ]
    dust_lines = [
        f"{icon} **{qty:,}** · `{key}` · *Dust ({stars_to_str(stars)})*"
        for icon, qty, key, _label, stars in dust_specs
        if qty > 0
    ]
    return base + dust_lines

def format_inventory_header(user: discord.abc.User) -> str:
    return "## Inventory\n" f"Items carried by {user.mention}\n\n"

def format_items_page(items: List[str]) -> str:
    if not items:
        return ""
    return "\n".join(items) + "\n"

PAGE_SIZE_COLLECTION = 10

PAGE_SIZE_COLLECTION = 10

def format_collection_page(rows: list[tuple], page: int, page_size: int) -> str:
    start = page * page_size
    end = start + page_size
    page_rows = rows[start:end]

    if not page_rows:
        return "_No cards to show._"

    lines = []
    for r in page_rows:
        uid, serial, stars, set_id, series, character, _condition, tag_emoji = r

        stars_str  = stars_to_str(int(stars))
        uid_box    = f"`{uid}`"
        stars_box  = f"`{stars_str}`"
        serial_box = f"`#{serial}`"
        setid_box  = f"`◈{set_id}`"

        lines.append(
            f"{tag_emoji} {uid_box} · {stars_box} · {serial_box} · {setid_box} · {series} · **{character}**"
        )

    return "\n".join(lines)

class InventoryView(discord.ui.View):
    def __init__(self, bot: commands.Bot, target: discord.abc.User, items: List[str], *, ephemeral: bool = False):
        super().__init__(timeout=120)
        self.bot = bot
        self.target = target
        self.items_all = items
        self.page = 0
        self.page_size = PAGE_SIZE_ITEMS
        self.pages = math.ceil(len(items) / self.page_size) if items else 1
        self.ephemeral = ephemeral
        if self.pages <= 1:
            self.clear_items()
        else:
            self._update_buttons()

    def _update_buttons(self):
        disable_prev = self.page <= 0
        disable_next = self.page >= self.pages - 1
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id in {"first_i", "prev_i"}:
                    child.disabled = disable_prev
                elif child.custom_id in {"next_i", "last_i"}:
                    child.disabled = disable_next

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(color=discord.Color.blurple())
        embed.description = format_inventory_header(self.target)
        total = len(self.items_all)
        if total > 0:
            current_items = slice_page(self.items_all, self.page, self.page_size)
            embed.description += format_items_page(current_items)
            embed.set_footer(text=page_range_text(self.page, total, self.page_size, "items"))
        return embed

    async def refresh(self, interaction: discord.Interaction):
        if self.pages > 1:
            self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, custom_id="first_i")
    async def first(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        await self.refresh(interaction)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary, custom_id="prev_i")
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        await self.refresh(interaction)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary, custom_id="next_i")
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.pages - 1:
            self.page += 1
        await self.refresh(interaction)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="last_i")
    async def last(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = self.pages - 1
        await self.refresh(interaction)

class CollectionView(discord.ui.View):
    def __init__(self, bot: commands.Bot, target: discord.abc.User, rows: List[Tuple], *, ephemeral: bool = False):
        super().__init__(timeout=120)
        self.bot = bot
        self.target = target
        self.rows = rows
        self.page = 0
        self.page_size = PAGE_SIZE_COLLECTION
        self.pages = math.ceil(len(rows) / self.page_size) if rows else 1
        self.ephemeral = ephemeral
        if self.pages <= 1:
            self.clear_items()
        else:
            self._update_buttons()

    def _update_buttons(self):
        disable_prev = self.page <= 0
        disable_next = self.page >= self.pages - 1
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id in {"first_c", "prev_c"}:
                    child.disabled = disable_prev
                elif child.custom_id in {"next_c", "last_c"}:
                    child.disabled = disable_next

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(color=discord.Color.blurple())
        embed.description = f"## Card Collection\nCards owned by {self.target.mention}\n\n"
        embed.description += format_collection_page(self.rows, self.page, self.page_size)
        embed.set_footer(text=page_range_text(self.page, len(self.rows), self.page_size, "cards"))
        return embed

    async def refresh(self, interaction: discord.Interaction):
        if self.pages > 1:
            self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, custom_id="first_c")
    async def first(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        await self.refresh(interaction)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary, custom_id="prev_c")
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        await self.refresh(interaction)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary, custom_id="next_c")
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.pages - 1:
            self.page += 1
        await self.refresh(interaction)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="last_c")
    async def last(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = self.pages - 1
        await self.refresh(interaction)

REWARD_BY_STARS = {0: 1, 1: 5, 2: 12, 3: 35, 4: 75}

def build_burn_preview_embed(requester: discord.abc.User, stars: int) -> discord.Embed:
    coins = REWARD_BY_STARS.get(stars, 0)
    dust = f"✨ 1 Dust ({stars_to_str(stars)})"
    gold = f"💰 {coins} Gold"
    desc = f"{requester.mention}, you will receive:\n\n{gold}\n{dust}"
    return discord.Embed(title="Burn Card", description=desc, color=discord.Color.dark_grey())

def build_burn_result_embed(base: discord.Embed, text: str, color: discord.Color) -> discord.Embed:
    e = discord.Embed(title=base.title, description=base.description + f"\n\n{text}", color=color)
    return e

class ConfirmBurnView(discord.ui.View):
    def __init__(self, bot: commands.Bot, requester_id: int, card_uid: str, stars: int):
        super().__init__(timeout=30)
        self.bot = bot
        self.requester_id = requester_id
        self.card_uid = card_uid
        self.stars = stars
        self._done = False

    async def interaction_guard(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("Only the requester can use these buttons.", ephemeral=True)
            return False
        return True

    async def finalize(self, interaction: discord.Interaction, embed: discord.Embed, color: discord.Color, text: str):
        self._done = True
        for c in self.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True
        await interaction.response.edit_message(embed=build_burn_result_embed(embed, text, color), view=self)

    @discord.ui.button(emoji="❌", style=discord.ButtonStyle.secondary, custom_id="burn_cancel")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.interaction_guard(interaction):
            return
        await self.finalize(interaction, interaction.message.embeds[0], discord.Color.red(), "Card burning has been canceled.")

    @discord.ui.button(emoji="🔥", style=discord.ButtonStyle.secondary, custom_id="burn_confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.interaction_guard(interaction):
            return
        reward = await self.bot.db.burn(self.card_uid, self.requester_id)
        if reward is None:
            await self.finalize(interaction, interaction.message.embeds[0], discord.Color.red(), "You don't own that card or it doesn't exist.")
            return
        await self.finalize(interaction, interaction.message.embeds[0], discord.Color.green(), "The card has been burned.")

    async def on_timeout(self):
        if self._done:
            return
        try:
            msg = self.message
        except AttributeError:
            return
        for c in self.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True
        base = msg.embeds[0] if msg.embeds else discord.Embed(title="Burn Card", color=discord.Color.dark_grey())
        timed = build_burn_result_embed(base, "Card burning timed out.", discord.Color.red())
        try:
            await msg.edit(embed=timed, view=self)
        except Exception:
            pass

class InventoryCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

    @app_commands.command(name="inventory", description="Show your items (coin, gem, ticket) with pagination.")
    @app_commands.describe(user="User to view, defaults to you")
    async def slash_inventory(self, interaction: discord.Interaction, user: discord.User | None = None):
        target = user or interaction.user
        bal = await self.bot.db.get_items(target.id)
        items_all = balances_to_items(bal) + get_other_items_for_user(target.id)
        view = InventoryView(self.bot, target, items_all, ephemeral=True)
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=False)

    @commands.command(name="i", aliases=["mi"])
    async def cmd_inventory_items(self, ctx: commands.Context, member: discord.Member | None = None):
        target = member or ctx.author
        bal = await self.bot.db.get_items(target.id)
        items_all = balances_to_items(bal) + get_other_items_for_user(target.id)
        view = InventoryView(self.bot, target, items_all)
        await ctx.send(embed=view.build_embed(), view=view)

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
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="give", description="Transfer a card to another user.")
    @app_commands.describe(card_id="Card UID", user="Recipient")
    async def slash_give(self, interaction: discord.Interaction, card_id: str, user: discord.User):
        ok = await self.bot.db.transfer(card_id.strip(), interaction.user.id, user.id)
        if not ok:
            return await interaction.response.send_message("You don't own that card or it doesn't exist.", ephemeral=True)
        await self.bot.db.ensure_user(user.id)
        await interaction.response.send_message(f"Transferred `{card_id}` to {user.mention}.")

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

    @commands.command(name="view", aliases=["mv", "v"])
    async def cmd_view(self, ctx: commands.Context, card_id: str | None = None):
        if card_id:
            card = await self.bot.db.get_card(card_id.strip())
        else:
            card = await self.bot.db.get_latest_card(ctx.author.id)

        if not card:
            return await ctx.send("Card not found.")

        embed = build_simple_cardinfo_embed(card)
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
    
    @commands.command(name="lookup", aliases=["mlu", "lu"])
    async def cmd_lookup(self, ctx: commands.Context, *, query: str | None = None):
        if not query:
            latest = await self.bot.db.get_latest_card(ctx.author.id)
            if not latest:
                return await ctx.send("You don't own any cards yet.")
            series = latest["series"]
            character = latest["character"]
            set_id = latest["set_id"]
            stats = await self.bot.db.character_stats(series, character, set_id=set_id)
            edition_index = 1
            embed = build_character_lookup_embed(stats, edition_index)
            return await ctx.send(embed=embed)

        parts = [p.strip() for p in query.split("|")]
        if len(parts) != 2:
            return await ctx.send("Format: `Series | Character` (or just `mlu` for your latest card)")

        series, character = parts
        stats_all = await self.bot.db.character_stats(series, character, set_id=None)
        editions = stats_all["editions"]
        if editions:
            set_id = editions[0]
            stats = await self.bot.db.character_stats(series, character, set_id=set_id)
            edition_index = 1
        else:
            stats = stats_all
            edition_index = 1

        embed = build_character_lookup_embed(stats, edition_index=edition_index)
        await ctx.send(embed=embed)

    @commands.command(name="tags")
    async def cmd_tags(self, ctx: commands.Context):
        tags = await self.bot.db.list_tags(ctx.author.id)
        if not tags:
            return await ctx.send("You have no tags yet. Create one with `mtc <name> <emoji>`.")
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
            return await ctx.send(f"⚠️ Tag `{tag_name}` not found. Use `mtc <name> <emoji>` first.")
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
