from __future__ import annotations
import time
import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from ..config import DROP_COOLDOWN_S, CLAIM_WINDOW_S, EMOJIS
from ..helpers import make_single_card_payload
from ..embeds import build_triple_drop_embed, format_card_embed

class DropsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot

    async def _get_active_drop_channel(self, guild_id: int) -> int | None:
        return await self.bot.db.get_drop_channel(guild_id)

    async def _cooldown_for(self, guild_id: int) -> int:
        v = await self.bot.db.get_drop_cooldown(guild_id)
        return v if v is not None else DROP_COOLDOWN_S

    async def create_three_cards(self, invoker_id: int, guild_id: int):
        cards = []
        for _ in range(3):
            payload = await make_single_card_payload(self.bot.db, invoker_id, guild_id)
            serial = await self.bot.db.next_serial()
            payload["serial_number"] = serial
            await self.bot.db.insert_dropped_card(payload)
            cards.append(payload)
        return cards

    async def add_number_reactions(self, message: discord.Message):
        for e in EMOJIS:
            try:
                await message.add_reaction(e)
            except Exception:
                pass

    async def expire_message_if_unclaimed(self, message_id: int):
        await asyncio.sleep(CLAIM_WINDOW_S)
        drop = self.bot.active_drops.get(message_id)
        if not drop or drop.get("claimed"):
            return
        drop["claimed"] = True
        try:
            channel = self.bot.get_channel(drop["channel_id"]) or await self.bot.fetch_channel(drop["channel_id"])
            msg = await channel.fetch_message(message_id)
            try:
                await msg.clear_reactions()
            except Exception:
                pass
            await msg.edit(content="Drop expired.")
        except Exception:
            pass
        finally:
            self.bot.active_drops.pop(message_id, None)

    @app_commands.command(name="drop", description="Drop 3 cards in this channel.")
    async def slash_drop(self, interaction: discord.Interaction):
        ch_id = interaction.channel_id
        active = await self._get_active_drop_channel(interaction.guild_id)
        if active is not None and ch_id != active:
            return await interaction.response.send_message(f"Drops are only allowed in <#{active}>.", ephemeral=True)

        cd = await self._cooldown_for(interaction.guild_id)
        now = time.time()
        last = self.bot.channel_cooldowns.get(ch_id, 0)
        if now - last < cd:
            remain = int(cd - (now - last))
            return await interaction.response.send_message(f"Please wait {remain}s before dropping again in this channel.", ephemeral=True)

        await self.bot.db.ensure_user(interaction.user.id)
        cards = await self.create_three_cards(interaction.user.id, interaction.guild_id)
        embed = build_triple_drop_embed(cards)
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        start_ts = time.time()
        self.bot.active_drops[msg.id] = {
            "cards": [c["card_uid"] for c in cards],
            "dropped_at": start_ts,
            "channel_id": ch_id,
            "guild_id": interaction.guild_id,
            "claimed": False,
        }
        self.bot.channel_cooldowns[ch_id] = now

        asyncio.create_task(self.add_number_reactions(msg))
        asyncio.create_task(self.expire_message_if_unclaimed(msg.id))

    @commands.command(name="d", aliases=["md"])
    async def cmd_drop(self, ctx: commands.Context):
        ch_id = ctx.channel.id
        active = await self._get_active_drop_channel(ctx.guild.id)
        if active is not None and ch_id != active:
            return await ctx.send(f"Drops are only allowed in <#{active}>.")

        cd = await self._cooldown_for(ctx.guild.id)
        now = time.time()
        last = self.bot.channel_cooldowns.get(ch_id, 0)
        if now - last < cd:
            remain = int(cd - (now - last))
            return await ctx.send(f"Please wait {remain}s before dropping again in this channel.")

        await self.bot.db.ensure_user(ctx.author.id)
        cards = await self.create_three_cards(ctx.author.id, ctx.guild.id)
        embed = build_triple_drop_embed(cards)
        sent = await ctx.send(embed=embed)

        start_ts = time.time()
        self.bot.active_drops[sent.id] = {
            "cards": [c["card_uid"] for c in cards],
            "dropped_at": start_ts,
            "channel_id": ch_id,
            "guild_id": ctx.guild.id,
            "claimed": False,
        }
        self.bot.channel_cooldowns[ch_id] = now

        asyncio.create_task(self.add_number_reactions(sent))
        asyncio.create_task(self.expire_message_if_unclaimed(sent.id))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not self.bot.user or payload.user_id == self.bot.user.id:
            return

        drop = self.bot.active_drops.get(payload.message_id)
        if not drop or drop.get("claimed"):
            return

        emoji = str(payload.emoji)
        if emoji not in EMOJIS:
            return

        now = time.time()
        if now - drop["dropped_at"] > CLAIM_WINDOW_S:
            drop["claimed"] = True
            try:
                channel = self.bot.get_channel(drop["channel_id"]) or await self.bot.fetch_channel(drop["channel_id"])
                msg = await channel.fetch_message(payload.message_id)
                try:
                    await msg.clear_reactions()
                except Exception:
                    pass
                await msg.edit(content="Drop expired.")
            except Exception:
                pass
            self.bot.active_drops.pop(payload.message_id, None)
            return

        idx = EMOJIS.index(emoji)
        if idx >= len(drop["cards"]):
            return
        card_uid = drop["cards"][idx]

        raw_delay = now - drop["dropped_at"]
        latency = float(getattr(self.bot, "latency", 0.0) or 0.0)
        delay = round(max(0.0, raw_delay - latency), 2)

        ok = await self.bot.db.claim_card(card_uid, payload.user_id, delay)
        if not ok:
            drop["claimed"] = True
            try:
                channel = self.bot.get_channel(drop["channel_id"]) or await self.bot.fetch_channel(drop["channel_id"])
                msg = await channel.fetch_message(payload.message_id)
                try:
                    await msg.clear_reactions()
                except Exception:
                    pass
                await msg.edit(content="This drop is already claimed.")
            except Exception:
                pass
            self.bot.active_drops.pop(payload.message_id, None)
            return

        drop["claimed"] = True
        try:
            channel = self.bot.get_channel(drop["channel_id"]) or await self.bot.fetch_channel(drop["channel_id"])
            msg = await channel.fetch_message(payload.message_id)
            card = await self.bot.db.get_card(card_uid)
            embed = format_card_embed(card, claimed=True)
            try:
                await msg.clear_reactions()
            except Exception:
                pass
            await msg.edit(embed=embed, content=None)
        except Exception:
            pass
        finally:
            self.bot.active_drops.pop(payload.message_id, None)

async def setup(bot: commands.Bot):
    await bot.add_cog(DropsCog(bot))
