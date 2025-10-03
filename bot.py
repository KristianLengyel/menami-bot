import os
from dotenv import load_dotenv
from menami.config import INTENTS, DROP_COOLDOWN_S
from menami.db import DB
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise SystemExit("Missing DISCORD_TOKEN in .env")

class MenamiBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned_or("m", "!"), intents=INTENTS)
        self.db = DB()
        self.channel_cooldowns: dict[int, float] = {}
        self.active_drops: dict[int, dict] = {}

    async def setup_hook(self):
        await self.db.init()
        await self.load_extension("menami.cogs.drops")
        await self.load_extension("menami.cogs.inventory")
        await self.load_extension("menami.cogs.helpcmd")
        await self.load_extension("menami.cogs.settings")
        await self.tree.sync()

bot = MenamiBot()
bot.remove_command("help")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id}) • cooldown={DROP_COOLDOWN_S}s")

if __name__ == "__main__":
    bot.run(TOKEN)
