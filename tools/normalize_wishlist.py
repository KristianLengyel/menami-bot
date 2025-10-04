import asyncio
from pathlib import Path
import sys

# add project root (parent of /tools) to sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from menami.db import DB  # now this works

async def main():
    db = DB()
    # if you haven't added this method yet, see snippet below
    await db.normalize_wishlist_rows()
    print("✅ Wishlist rows normalized (TRIM applied).")

if __name__ == "__main__":
    asyncio.run(main())
