import discord

INTENTS = discord.Intents.default()
INTENTS.message_content = True

DB_PATH = "menami.db"

USER_DROP_COOLDOWN_S = 30
GRAB_COOLDOWN_S      = 5

DAILY_COOLDOWN_S = 24 * 60 * 60
DAILY_COINS_MIN, DAILY_COINS_MAX = 100, 500
DAILY_GEMS_MIN,  DAILY_GEMS_MAX  = 10,  30

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

UPGRADE_RULES = {
    0: {"to": 1, "chance": 0.80, "gold": 50,  "dust": 5, "fail": "stay"},
    1: {"to": 2, "chance": 0.70, "gold": 100, "dust": 5, "fail": "damaged"},
    2: {"to": 3, "chance": 0.60, "gold": 250, "dust": 5, "fail": "damaged"},
    3: {"to": 4, "chance": 0.50, "gold": 500, "dust": 5, "fail": "damaged"},
}