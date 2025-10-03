from __future__ import annotations
from typing import List, Tuple
import math
import discord
from discord.ext import commands
from .embeds import build_burn_preview_embed, build_burn_result_embed
from .helpers import stars_to_str

PAGE_SIZE_ITEMS = 10
PAGE_SIZE_COLLECTION = 10

def page_range_text(page: int, total: int, page_size: int, noun: str) -> str:
    if total == 0:
        return f"Showing {noun} 0–0 of 0"
    start = page * page_size + 1
    end = min((page + 1) * page_size, total)
    return f"Showing {noun} {start}–{end} of {total}"

def slice_page(items: List[str], page: int, page_size: int) -> List[str]:
    start = page * page_size
    end = start + page_size
    return items[start:end]

def format_inventory_header(user: discord.abc.User) -> str:
    return "## Inventory\n" f"Items carried by {user.mention}\n\n"

def format_items_page(items: List[str]) -> str:
    if not items:
        return ""
    return "\n".join(items) + "\n"

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

def balances_to_items(bal: dict) -> List[str]:
    base = [
        f":coin: **{bal['coins']:,}** · `coin` · *Coin*",
        f":gem: **{bal['gems']:,}** · `gem` · *Gem*",
        f"🎟️ **{bal['tickets']:,}** · `ticket` · *Ticket*",
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
