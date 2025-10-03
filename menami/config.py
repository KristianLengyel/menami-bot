import discord

INTENTS = discord.Intents.default()
INTENTS.message_content = True

DB_PATH = "menami.db"

DROP_COOLDOWN_S = 30
CLAIM_WINDOW_S = 60

STAR_MIN = 0
STAR_MAX = 4

STAR_WEIGHTS = [10, 20, 40, 20, 10]

EMOJIS = ["1️⃣", "2️⃣", "3️⃣"]

QUALITY_BY_STARS = {
    0: "damaged",
    1: "poor",
    2: "good",
    3: "excellent",
    4: "mint",
}

BURN_REWARD_BY_STARS = {
    0: 9,    # ☆☆☆☆
    1: 19,   # ★☆☆☆
    2: 30,   # ★★☆☆
    3: 63,   # ★★★☆
    4: 124,  # ★★★★
}
