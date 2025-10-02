import asyncio
import json
import sys
from menami.db import DB

async def main(path: str):
    db = DB()
    await db.init()

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    for series, chars in data.items():
        for char in chars:
            await db.insert_character(series.strip(), char.strip())
            count += 1

    print(f"✅ Seeded {count} characters from JSON")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python tools/seed_json.py data/characters.json")
        raise SystemExit(1)
    asyncio.run(main(sys.argv[1]))
