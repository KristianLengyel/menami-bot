from __future__ import annotations
import json
import aiosqlite
import random
from datetime import datetime, timezone
from .config import DB_PATH, QUALITY_BY_STARS, BURN_REWARD_BY_STARS

def _utcnow_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

def _parse_iso(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

class DB:
    def __init__(self, path: str = DB_PATH):
        self.path = path

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.executescript("""
            PRAGMA foreign_keys=ON;
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS users(
              user_id INTEGER PRIMARY KEY,
              coins   INTEGER NOT NULL DEFAULT 0,
              gems    INTEGER NOT NULL DEFAULT 0,
              tickets INTEGER NOT NULL DEFAULT 0,
              dust_damaged  INTEGER NOT NULL DEFAULT 0,
              dust_poor     INTEGER NOT NULL DEFAULT 0,
              dust_good     INTEGER NOT NULL DEFAULT 0,
              dust_excellent INTEGER NOT NULL DEFAULT 0,
              dust_mint     INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS cards(
              card_uid TEXT PRIMARY KEY,
              serial_number INTEGER NOT NULL,
              stars INTEGER NOT NULL,
              set_id INTEGER NOT NULL,
              series TEXT NOT NULL,
              character TEXT NOT NULL,
              condition TEXT NOT NULL,
              dropped_at TEXT NOT NULL,
              dropped_in_server TEXT NOT NULL,
              dropped_by TEXT NOT NULL,
              grabbed_by TEXT,
              owned_by TEXT,
              grab_delay REAL
            );

            CREATE TABLE IF NOT EXISTS burns(
              card_uid   TEXT PRIMARY KEY,
              series     TEXT NOT NULL,
              character  TEXT NOT NULL,
              stars      INTEGER NOT NULL,
              set_id     INTEGER NOT NULL,
              grabbed_by TEXT,
              grab_delay REAL,
              owner_id   TEXT NOT NULL,
              burned_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tags(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                emoji TEXT NOT NULL,
                UNIQUE(user_id, name)
            );

            CREATE TABLE IF NOT EXISTS card_tags(
                card_uid TEXT NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY(card_uid),
                FOREIGN KEY(card_uid) REFERENCES cards(card_uid),
                FOREIGN KEY(tag_id) REFERENCES tags(id)
            );
                                   
            CREATE TABLE IF NOT EXISTS character_images(
                series    TEXT NOT NULL,
                character TEXT NOT NULL,
                set_id    INTEGER NOT NULL,
                image_url TEXT NOT NULL,
                bytes     INTEGER,
                mime      TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(series, character, set_id)
            );

            CREATE TABLE IF NOT EXISTS meta(
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS series(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS characters(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              series_id INTEGER NOT NULL,
              name TEXT NOT NULL,
              FOREIGN KEY(series_id) REFERENCES series(id),
              UNIQUE(series_id, name)
            );

            CREATE TABLE IF NOT EXISTS guild_settings(
              guild_id TEXT PRIMARY KEY,
              drop_channel_id TEXT,
              drop_cooldown_s INTEGER
            );
                                   
            CREATE TABLE IF NOT EXISTS user_timers(
                user_id TEXT NOT NULL,
                key     TEXT NOT NULL,
                ts      TEXT NOT NULL,
                PRIMARY KEY(user_id, key)
            );
                                   
            CREATE TABLE IF NOT EXISTS wishlists(
                user_id  TEXT NOT NULL,
                series   TEXT NOT NULL,
                character TEXT NOT NULL,
                PRIMARY KEY(user_id, series, character)
            );
                                   
            CREATE TABLE IF NOT EXISTS user_dyes(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id TEXT NOT NULL,
              code TEXT NOT NULL UNIQUE,
              color_hex TEXT NOT NULL,
              charges INTEGER NOT NULL DEFAULT 0,
              name TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
                                   
            CREATE TABLE IF NOT EXISTS card_dyes(
                card_uid  TEXT PRIMARY KEY,
                code      TEXT NOT NULL,
                color_hex TEXT NOT NULL,
                name      TEXT NOT NULL,
                applied_at TEXT NOT NULL,
                FOREIGN KEY(card_uid) REFERENCES cards(card_uid)
            );
                 
            CREATE INDEX IF NOT EXISTS idx_user_dyes_user ON user_dyes(user_id, created_at);            
            CREATE INDEX IF NOT EXISTS idx_cards_owned_by ON cards(owned_by);
            CREATE INDEX IF NOT EXISTS idx_cards_series_character ON cards(series, character);
            CREATE INDEX IF NOT EXISTS idx_cards_series_character_set ON cards(series, character, set_id);
            CREATE INDEX IF NOT EXISTS idx_burns_series_character ON burns(series, character);
            CREATE INDEX IF NOT EXISTS idx_burns_series_character_set ON burns(series, character, set_id);
            CREATE INDEX IF NOT EXISTS idx_cards_owned_by_dropped_at ON cards(owned_by, dropped_at);
            CREATE INDEX IF NOT EXISTS idx_wish_series_char ON wishlists(series, character);
            CREATE INDEX IF NOT EXISTS idx_wish_user ON wishlists(user_id);

            CREATE UNIQUE INDEX IF NOT EXISTS uq_cards_series_character_set_serial
            ON cards(series, character, set_id, serial_number);
                                
            INSERT OR IGNORE INTO meta(key, value) VALUES('next_serial', '1');
            INSERT OR IGNORE INTO meta(key, value) VALUES('editions_max', '5');
            INSERT OR IGNORE INTO meta(key, value) VALUES('edition_weights', '[1,2,3,5,9]');
            """)
            # --- MIGRATIONS: add thickness columns if missing ---
            cols_ud = {row[1] for row in await (await db.execute("PRAGMA table_info(user_dyes)")).fetchall()}
            if "thickness" not in cols_ud:
                await db.execute("ALTER TABLE user_dyes ADD COLUMN thickness INTEGER NOT NULL DEFAULT 8")

            cols_cd = {row[1] for row in await (await db.execute("PRAGMA table_info(card_dyes)")).fetchall()}
            if "thickness" not in cols_cd:
                await db.execute("ALTER TABLE card_dyes ADD COLUMN thickness INTEGER NOT NULL DEFAULT 8")
            # ----------------------------------------------------
            cols_u = {row[1] for row in await (await db.execute("PRAGMA table_info(users)")).fetchall()}
            for col in ["gems", "tickets", "dust_damaged", "dust_poor", "dust_good", "dust_excellent", "dust_mint"]:
                if col not in cols_u:
                    await db.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
            cols_g = {row[1] for row in await (await db.execute("PRAGMA table_info(guild_settings)")).fetchall()}
            if "drop_cooldown_s" not in cols_g:
                await db.execute("ALTER TABLE guild_settings ADD COLUMN drop_cooldown_s INTEGER")
            await db.commit()

    async def _random_free_serial(self, series: str, character: str, set_id: int, *, max_tries: int = 50) -> int:
        for _ in range(max_tries):
            sn = random.randint(1, 9999)
            async with aiosqlite.connect(self.path) as db:
                cur = await db.execute(
                    """SELECT 1 FROM cards
                       WHERE series=? AND character=? AND set_id=? AND serial_number=? LIMIT 1""",
                    (series, character, set_id, sn),
                )
                if not await cur.fetchone():
                    return sn
        used = set()
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """SELECT serial_number FROM cards
                   WHERE series=? AND character=? AND set_id=?""",
                (series, character, set_id),
            )
            rows = await cur.fetchall()
            used.update(int(r[0]) for r in rows if r and r[0] is not None)
        for sn in range(1, 10000):
            if sn not in used:
                return sn
        raise RuntimeError("All serial numbers 1..9999 are taken for this edition.")

    async def get_drop_channel(self, guild_id: int) -> int | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT drop_channel_id FROM guild_settings WHERE guild_id=?", (str(guild_id),))
            row = await cur.fetchone()
            return int(row[0]) if row and row[0] is not None else None

    async def set_drop_channel(self, guild_id: int, channel_id: int | None):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO guild_settings(guild_id, drop_channel_id) VALUES(?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET drop_channel_id=excluded.drop_channel_id",
                (str(guild_id), str(channel_id) if channel_id is not None else None),
            )
            await db.commit()

    async def get_drop_cooldown(self, guild_id: int) -> int | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT drop_cooldown_s FROM guild_settings WHERE guild_id=?", (str(guild_id),))
            row = await cur.fetchone()
            return int(row[0]) if row and row[0] is not None else None

    async def set_drop_cooldown(self, guild_id: int, seconds: int | None):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT INTO guild_settings(guild_id) VALUES(?) ON CONFLICT(guild_id) DO NOTHING", (str(guild_id),))
            await db.execute("UPDATE guild_settings SET drop_cooldown_s=? WHERE guild_id=?", (seconds, str(guild_id)))
            await db.commit()

    # ---------- dyes ----------
    async def create_user_dye(self, user_id: int, code: str, color_hex: str, charges: int, name: str, thickness: int):
        ts = _utcnow_iso()
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO user_dyes(user_id, code, color_hex, charges, name, created_at, thickness) VALUES(?,?,?,?,?,?,?)",
                (str(user_id), code, color_hex, int(charges), name, ts, int(thickness))
            )
            await db.commit()

    async def list_user_dyes(self, user_id: int) -> list[tuple[str,str,int,str,int]]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT code, color_hex, charges, name, thickness FROM user_dyes WHERE user_id=? ORDER BY datetime(created_at) DESC",
                (str(user_id),)
            )
            rows = await cur.fetchall()
            return [(r[0], r[1], int(r[2]), r[3], int(r[4])) for r in rows]

    async def get_user_dye(self, user_id: int, code: str) -> tuple[str, str, int, str, int] | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT code, color_hex, charges, name, thickness FROM user_dyes WHERE user_id=? AND LOWER(code)=LOWER(?)",
                (str(user_id), code)
            )
            row = await cur.fetchone()
            return (row[0], row[1], int(row[2]), row[3], int(row[4])) if row else None

    async def consume_user_dye(self, user_id: int, code: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "UPDATE user_dyes SET charges = charges - 1 WHERE user_id=? AND LOWER(code)=LOWER(?) AND charges > 0",
                (str(user_id), code)
            )
            await db.commit()
            return cur.rowcount == 1

    async def set_card_dye(self, card_uid: str, code: str, color_hex: str, name: str, thickness: int):
        ts = _utcnow_iso()
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                INSERT INTO card_dyes(card_uid, code, color_hex, name, applied_at, thickness)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(card_uid) DO UPDATE SET
                    code=excluded.code,
                    color_hex=excluded.color_hex,
                    name=excluded.name,
                    applied_at=excluded.applied_at,
                    thickness=excluded.thickness
            """, (card_uid, code, color_hex, name, ts, int(thickness)))
            await db.commit()

    async def get_card_dye(self, card_uid: str) -> tuple[str, str, str, str, int] | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT card_uid, code, color_hex, name, thickness FROM card_dyes WHERE card_uid=?", (card_uid,))
            row = await cur.fetchone()
            return (row[0], row[1], row[2], row[3], int(row[4])) if row else None


    async def remove_card_dye(self, card_uid: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM card_dyes WHERE card_uid=?", (card_uid,))
            await db.commit()

    async def user_owns_card(self, user_id: int, card_uid: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT 1 FROM cards WHERE card_uid=? AND owned_by=?", (card_uid, str(user_id)))
            return (await cur.fetchone()) is not None

    # ---------- wishlist ----------
    async def wishlist_count(self, user_id: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM wishlists WHERE user_id=?", (str(user_id),))
            row = await cur.fetchone()
            return int(row[0] or 0)

    async def list_wishlist(self, user_id: int) -> list[tuple[str, str]]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("""
                SELECT series, character
                FROM wishlists
                WHERE user_id=?
                ORDER BY LOWER(series) ASC, LOWER(character) ASC
            """, (str(user_id),))
            rows = await cur.fetchall()
            return [(r[0], r[1]) for r in rows]

    async def add_wish(self, user_id: int, series: str, character: str) -> bool:
        series = (series or "").strip()
        character = (character or "").strip()

        canon = await self.find_canonical_series_character(series, character)
        if canon:
            series, character = canon

        async with aiosqlite.connect(self.path) as db:
            try:
                await db.execute("""
                    INSERT INTO wishlists(user_id, series, character)
                    VALUES(?,?,?)
                    ON CONFLICT(user_id, series, character) DO NOTHING
                """, (str(user_id), series, character))
                await db.commit()

                cur = await db.execute("""
                    SELECT 1 FROM wishlists
                    WHERE user_id=? AND series=? AND character=?
                    LIMIT 1
                """, (str(user_id), series, character))
                return await cur.fetchone() is not None
            except Exception:
                return False

    async def remove_wish(self, user_id: int, series: str | None, character: str) -> int:
        async with aiosqlite.connect(self.path) as db:
            if series:
                cur = await db.execute("""
                    DELETE FROM wishlists WHERE user_id=? AND LOWER(series)=LOWER(?) AND LOWER(character)=LOWER(?)
                """, (str(user_id), series, character))
            else:
                cur = await db.execute("""
                    DELETE FROM wishlists WHERE user_id=? AND LOWER(character)=LOWER(?)
                """, (str(user_id), character))
            await db.commit()
            return cur.rowcount or 0

    async def find_canonical_series_character(self, series: str, character: str) -> tuple[str, str] | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("""
                SELECT s.name, c.name
                FROM characters c
                JOIN series s ON c.series_id = s.id
                WHERE LOWER(s.name)=LOWER(?) AND LOWER(c.name)=LOWER(?)
                LIMIT 1
            """, (series, character))
            row = await cur.fetchone()
            return (row[0], row[1]) if row else None

    async def find_by_character_only(self, character: str) -> list[tuple[str, str]]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("""
                SELECT s.name, c.name
                FROM characters c
                JOIN series s ON c.series_id = s.id
                WHERE LOWER(c.name)=LOWER(?)
                ORDER BY LOWER(s.name) ASC
            """, (character,))
            rows = await cur.fetchall()
            return [(r[0], r[1]) for r in rows]

    async def get_wishers_for(self, series: str, character: str) -> list[int]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("""
                SELECT user_id FROM wishlists
                WHERE LOWER(series)=LOWER(?) AND LOWER(character)=LOWER(?)
            """, (series, character))
            rows = await cur.fetchall()
            return [int(r[0]) for r in rows]

    # ---------- timers ----------
    async def set_timer(self, user_id: int, key: str):
        ts = _utcnow_iso()
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                INSERT INTO user_timers(user_id, key, ts) VALUES(?, ?, ?)
                ON CONFLICT(user_id, key) DO UPDATE SET ts=excluded.ts
            """, (str(user_id), key, ts))
            await db.commit()

    async def get_timer(self, user_id: int, key: str) -> str | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT ts FROM user_timers WHERE user_id=? AND key=?", (str(user_id), key))
            row = await cur.fetchone()
            return row[0] if row else None

    async def seconds_remaining(self, user_id: int, key: str, cooldown_s: int) -> int:
        ts = await self.get_timer(user_id, key)
        if not ts:
            return 0
        last = _parse_iso(ts)
        now  = datetime.utcnow().replace(tzinfo=timezone.utc)
        elapsed = (now - last).total_seconds()
        remain = int(max(0, cooldown_s - elapsed))
        return remain

    # ---------- currency helpers ----------
    async def add_currency(self, user_id: int, *, coins: int = 0, gems: int = 0):
        await self.ensure_user(user_id)
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                UPDATE users SET coins = coins + ?, gems = gems + ? WHERE user_id=?
            """, (int(coins), int(gems), user_id))
            await db.commit()

    # ---- content helpers ----
    async def insert_series(self, name: str) -> int:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR IGNORE INTO series(name) VALUES(?)", (name,))
            await db.commit()
            cur = await db.execute("SELECT id FROM series WHERE name=?", (name,))
            row = await cur.fetchone()
            return int(row[0])

    async def insert_character(self, series_name: str, character_name: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR IGNORE INTO series(name) VALUES(?)", (series_name,))
            cur = await db.execute("SELECT id FROM series WHERE name=?", (series_name,))
            series_id = int((await cur.fetchone())[0])
            await db.execute("INSERT OR IGNORE INTO characters(series_id, name) VALUES(?, ?)", (series_id, character_name))
            await db.commit()

    async def random_series_character(self) -> tuple[str, str] | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("""
                SELECT s.name, c.name
                FROM characters c
                JOIN series s ON s.id = c.series_id
                ORDER BY RANDOM()
                LIMIT 1
            """)
            row = await cur.fetchone()
            return (row[0], row[1]) if row else None

    # ---- meta ----
    async def next_serial(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT value FROM meta WHERE key='next_serial'")
            row = await cur.fetchone()
            n = int(row[0])
            await db.execute("UPDATE meta SET value=? WHERE key='next_serial'", (str(n+1),))
            await db.commit()
            return n

    async def get_meta(self, key: str) -> str | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT value FROM meta WHERE key=?", (key,))
            row = await cur.fetchone()
            return row[0] if row else None

    async def set_meta(self, key: str, value: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                INSERT INTO meta(key, value) VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, value))
            await db.commit()

    def _autogen_weights(self, n: int, ratio: float = 1.6) -> list[int]:
        return [max(1, int(round(ratio ** i))) for i in range(n)]

    async def get_editions_config(self) -> tuple[int, list[int]]:
        n_default = 5
        w_default = self._autogen_weights(n_default)

        raw_n = await self.get_meta("editions_max")
        raw_w = await self.get_meta("edition_weights")

        try:
            n = int(raw_n) if raw_n is not None else n_default
        except Exception:
            n = n_default

        try:
            weights = json.loads(raw_w) if raw_w else w_default
            if not isinstance(weights, list) or not all(isinstance(x, (int, float)) for x in weights):
                raise ValueError
            weights = [int(max(1, round(float(x)))) for x in weights]
        except Exception:
            weights = w_default

        if len(weights) < n:
            extra_needed = n - len(weights)
            if weights:
                base = max(1, weights[-1])
                extra = []
                for i in range(extra_needed):
                    extra.append(max(1, int(round(base * (1.6 ** (i + 1))))))
                weights = weights + extra
            else:
                weights = self._autogen_weights(n)
        elif len(weights) > n:
            weights = weights[:n]

        return n, weights

    async def set_editions_config(self, n: int, weights: list[int] | None = None):
        if weights is None:
            weights = self._autogen_weights(n)
        weights = [int(max(1, w)) for w in weights]
        await self.set_meta("editions_max", str(int(n)))
        await self.set_meta("edition_weights", json.dumps(weights))

    # ---- users ----
    async def ensure_user(self, user_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                INSERT OR IGNORE INTO users(user_id, coins, gems, tickets)
                VALUES(?, 0, 0, 0)
            """, (user_id,))
            await db.commit()

    async def balance(self, user_id: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT coins FROM users WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def get_items(self, user_id: int) -> dict:
        await self.ensure_user(user_id)
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("""
                SELECT coins, gems, tickets,
                       dust_damaged, dust_poor, dust_good, dust_excellent, dust_mint
                FROM users WHERE user_id=?
            """, (user_id,))
            row = await cur.fetchone()
            if not row:
                return {"coins": 0, "gems": 0, "tickets": 0,
                        "dust_damaged": 0, "dust_poor": 0, "dust_good": 0, "dust_excellent": 0, "dust_mint": 0}
            coins, gems, tickets, dd, dp, dg, de, dm = row
            return {
                "coins": int(coins),
                "gems": int(gems),
                "tickets": int(tickets),
                "dust_damaged": int(dd),
                "dust_poor": int(dp),
                "dust_good": int(dg),
                "dust_excellent": int(de),
                "dust_mint": int(dm),
            }

    # ---- tags ----
    async def create_tag(self, user_id: int, name: str, emoji: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            try:
                await db.execute(
                    "INSERT INTO tags(user_id, name, emoji) VALUES(?,?,?)",
                    (str(user_id), name.lower(), emoji)
                )
                await db.commit()
                return True
            except Exception:
                return False

    async def delete_tag(self, user_id: int, name: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT id FROM tags WHERE user_id=? AND name=?",
                (str(user_id), name.lower())
            )
            row = await cur.fetchone()
            if not row:
                return False
            tag_id = row[0]
            await db.execute("DELETE FROM card_tags WHERE tag_id=?", (tag_id,))
            await db.execute("DELETE FROM tags WHERE id=?", (tag_id,))
            await db.commit()
            return True

    async def list_tags(self, user_id: int) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT id, name, emoji FROM tags WHERE user_id=? ORDER BY name",
                (str(user_id),)
            )
            rows = await cur.fetchall()
            return [{"id": r[0], "name": r[1], "emoji": r[2]} for r in rows]

    async def assign_tag(self, user_id: int, card_uid: str, tag_name: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT id FROM tags WHERE user_id=? AND name=?",
                (str(user_id), tag_name.lower())
            )
            row = await cur.fetchone()
            if not row:
                return False
            tag_id = row[0]
            await db.execute(
                "INSERT OR REPLACE INTO card_tags(card_uid, tag_id) VALUES(?,?)",
                (card_uid, tag_id)
            )
            await db.commit()
            return True

    async def untag_card(self, card_uid: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM card_tags WHERE card_uid=?", (card_uid,))
            await db.commit()

    async def get_card_tag(self, card_uid: str) -> str:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """SELECT t.emoji
                   FROM card_tags ct
                   JOIN tags t ON ct.tag_id = t.id
                   WHERE ct.card_uid=?""",
                (card_uid,)
            )
            row = await cur.fetchone()
            return row[0] if row else "◾"

    async def normalize_wishlist_rows(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('UPDATE wishlists SET series=TRIM(series), "character"=TRIM("character")')
            await db.commit()

    # ---- cards ----
    async def set_character_image(self, series: str, character: str, set_id: int,
                              image_url: str, bytes_: int | None = None, mime: str | None = None):
        ts = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                INSERT INTO character_images(series, character, set_id, image_url, bytes, mime, updated_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(series, character, set_id)
                DO UPDATE SET image_url=excluded.image_url,
                            bytes=excluded.bytes,
                            mime=excluded.mime,
                            updated_at=excluded.updated_at
            """, (series, character, int(set_id), image_url, bytes_, mime, ts))
            await db.commit()

    async def get_character_image(self, series: str, character: str, set_id: int) -> str | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("""
                SELECT image_url FROM character_images
                WHERE series=? AND character=? AND set_id=?
            """, (series, character, int(set_id)))
            row = await cur.fetchone()
            return row[0] if row else None

    async def get_character_image_any(self, series: str, character: str) -> str | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("""
                SELECT image_url FROM character_images
                WHERE series=? AND character=?
                ORDER BY set_id ASC LIMIT 1
            """, (series, character))
            row = await cur.fetchone()
            return row[0] if row else None
    
    async def inventory_filtered(self, user_id: int, flt: dict):
        where = ["c.owned_by=?"]
        params = [str(user_id)]

        if s := flt.get("s"):
            where.append("LOWER(c.series) LIKE ?")
            params.append(f"%{s.lower()}%")

        if ch := flt.get("c"):
            where.append("LOWER(c.character) LIKE ?")
            params.append(f"%{ch.lower()}%")

        q_op = flt.get("q_op")
        q_val = flt.get("q_val")
        if q_op and q_val is not None:
            where.append(f"c.stars {q_op} ?")
            params.append(int(q_val))
        elif (q := flt.get("q")) is not None:
            where.append("c.stars = ?")
            params.append(int(q))

        if "t" in flt:
            t = flt["t"].strip().lower()
            if t == "none":
                where.append("ct.tag_id IS NULL")
            else:
                where.append("LOWER(t.name) = ?")
                params.append(t)

        if (e := flt.get("e")) is not None:
            where.append("c.set_id = ?")
            params.append(int(e))

        order = flt.get("o", "d")
        if order == "s":
            order_by = "c.series ASC, c.character ASC, c.set_id ASC, c.dropped_at DESC"
        else:
            order_by = "c.dropped_at DESC"

        sql = f"""
        SELECT
            c.card_uid,
            c.serial_number,
            c.stars,
            c.set_id,
            c.series,
            c.character,
            c.condition,
            COALESCE(t.emoji, '◾') AS tag_emoji
        FROM cards c
        LEFT JOIN card_tags ct ON ct.card_uid = c.card_uid
        LEFT JOIN tags t ON t.id = ct.tag_id
        WHERE {' AND '.join(where)}
        ORDER BY {order_by}
        """
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(sql, params)
            return await cur.fetchall()

    async def insert_dropped_card(self, card: dict):
        series = card["series"]
        character = card["character"]
        set_id = int(card["set_id"])

        attempts = 0
        while True:
            attempts += 1
            serial_number = card.get("serial_number")
            if serial_number is None:
                serial_number = await self._random_free_serial(series, character, set_id)

            try:
                async with aiosqlite.connect(self.path) as db:
                    await db.execute("BEGIN IMMEDIATE")
                    await db.execute("""
                        INSERT INTO cards(
                            card_uid, serial_number, stars, set_id, series, character, condition,
                            dropped_at, dropped_in_server, dropped_by, grabbed_by, owned_by, grab_delay
                        )
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        card["card_uid"],
                        int(serial_number),
                        int(card["stars"]),
                        int(set_id),
                        series,
                        character,
                        card["condition"],
                        card["dropped_at"],
                        card["dropped_in_server"],
                        card["dropped_by"],
                        None, None, None
                    ))
                    await db.commit()
                return
            except aiosqlite.IntegrityError as e:
                if "uq_cards_series_character_set_serial" in str(e).lower():
                    card["serial_number"] = None
                    if attempts >= 20:
                        raise
                    continue
                else:
                    raise

    async def claim_card(self, card_uid: str, claimer_id: int, delay: float) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("""
                UPDATE cards
                   SET grabbed_by=?, owned_by=?, grab_delay=?
                 WHERE card_uid=? AND grabbed_by IS NULL
            """, (str(claimer_id), str(claimer_id), delay, card_uid))
            await db.commit()
            return cur.rowcount == 1

    async def get_card(self, card_uid: str) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT * FROM cards WHERE card_uid=?", (card_uid,))
            row = await cur.fetchone()
            if not row:
                return None
            cols = [c[0] for c in cur.description]
            return dict(zip(cols, row))

    async def inventory(self, user_id: int):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("""
            SELECT
                c.card_uid,
                c.serial_number,
                c.stars,
                c.set_id,
                c.series,
                c.character,
                c.condition,
                COALESCE(t.emoji, '◾') AS tag_emoji
            FROM cards c
            LEFT JOIN card_tags ct ON ct.card_uid = c.card_uid
            LEFT JOIN tags t ON t.id = ct.tag_id
            WHERE c.owned_by=?
            ORDER BY c.dropped_at DESC
            """, (str(user_id),))
            return await cur.fetchall()

    async def transfer(self, card_uid: str, from_id: int, to_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT owned_by FROM cards WHERE card_uid=?", (card_uid,))
            row = await cur.fetchone()
            if not row or row[0] != str(from_id):
                return False
            await db.execute("UPDATE cards SET owned_by=? WHERE card_uid=?", (str(to_id), card_uid))
            await db.commit()
            return True

    async def burn(self, card_uid: str, owner_id: int) -> int | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("""
                SELECT owned_by, stars, set_id, series, character, grabbed_by, grab_delay
                FROM cards WHERE card_uid=?
            """, (card_uid,))
            row = await cur.fetchone()
            if not row or row[0] != str(owner_id):
                return None

            owned_by, stars, set_id, series, character, grabbed_by, grab_delay = row
            stars = int(stars)
            reward = BURN_REWARD_BY_STARS.get(stars, 0)

            from datetime import datetime, timezone
            burned_at = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

            await db.execute("""
              INSERT OR REPLACE INTO burns(card_uid, series, character, stars, set_id, grabbed_by, grab_delay, owner_id, burned_at)
              VALUES(?,?,?,?,?,?,?,?,?)
            """, (card_uid, series, character, stars, set_id, grabbed_by, grab_delay, str(owner_id), burned_at))

            await db.execute("DELETE FROM cards WHERE card_uid=?", (card_uid,))

            quality = QUALITY_BY_STARS.get(stars, "damaged")
            dust_col = f"dust_{quality}"

            await db.execute("""
              INSERT INTO users(user_id, coins) VALUES(?, ?)
              ON CONFLICT(user_id) DO UPDATE SET coins = coins + excluded.coins
            """, (owner_id, reward))

            await db.execute(f"UPDATE users SET {dust_col} = {dust_col} + 1 WHERE user_id=?", (owner_id,))
            await db.commit()
            return reward

    async def character_stats(self, series: str, character: str, set_id: int | None = None) -> dict:
        canon = await self.find_canonical_series_character(series, character)
        if canon:
            series, character = canon

        params = [series, character]
        set_clause = ""
        if set_id is not None:
            set_clause = " AND set_id=?"
            params.append(set_id)

        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(f"""
                SELECT COUNT(*) AS total_current,
                    SUM(CASE WHEN grabbed_by IS NOT NULL THEN 1 ELSE 0 END) AS current_claimed,
                    AVG(CASE WHEN grab_delay IS NOT NULL THEN grab_delay END) AS current_avg_delay
                FROM cards
                WHERE series=? AND character=? {set_clause}
            """, params)
            current_total, current_claimed, current_avg_delay = await cur.fetchone() or (0, 0, None)
            current_total = int(current_total or 0)
            current_claimed = int(current_claimed or 0)
            current_avg_delay = float(current_avg_delay) if current_avg_delay is not None else None

            cur = await db.execute(f"""
                SELECT COUNT(*) AS burned_total,
                    SUM(CASE WHEN grabbed_by IS NOT NULL THEN 1 ELSE 0 END) AS burned_claimed,
                    AVG(CASE WHEN grab_delay IS NOT NULL THEN grab_delay END) AS burned_avg_delay
                FROM burns
                WHERE series=? AND character=? {set_clause}
            """, params)
            burned_total, burned_claimed, burned_avg_delay = await cur.fetchone() or (0, 0, None)
            burned_total = int(burned_total or 0)
            burned_claimed = int(burned_claimed or 0)
            burned_avg_delay = float(burned_avg_delay) if burned_avg_delay is not None else None

            cur = await db.execute(f"""
                SELECT stars, COUNT(*)
                FROM cards
                WHERE series=? AND character=? {set_clause} AND owned_by IS NOT NULL
                GROUP BY stars
            """, params)
            star_rows = await cur.fetchall()
            circ_by_stars = {int(s): int(c) for (s, c) in (star_rows or [])}

            cur = await db.execute("""
                SELECT COUNT(*)
                FROM wishlists w
                WHERE LOWER(REPLACE(REPLACE(REPLACE(TRIM(w.series), CHAR(160), ''), CHAR(8203), ''), ' ', ''))
                    = LOWER(REPLACE(REPLACE(REPLACE(TRIM(?),        CHAR(160), ''), CHAR(8203), ''), ' ', ''))
                AND LOWER(REPLACE(REPLACE(REPLACE(TRIM(w."character"), CHAR(160), ''), CHAR(8203), ''), ' ', ''))
                    = LOWER(REPLACE(REPLACE(REPLACE(TRIM(?),             CHAR(160), ''), CHAR(8203), ''), ' ', ''))
            """, (series, character))
            wishlisted = int((await cur.fetchone() or (0,))[0] or 0)

        total_generated = current_total + burned_total
        total_claimed   = current_claimed + burned_claimed
        claim_rate = (total_claimed / total_generated * 100.0) if total_generated else 0.0

        weighted = []
        if current_avg_delay is not None:
            weighted.append((current_avg_delay, current_claimed))
        if burned_avg_delay is not None:
            weighted.append((burned_avg_delay, burned_claimed))
        if weighted and sum(w for _, w in weighted):
            avg_delay = sum(a * w for a, w in weighted) / sum(w for _, w in weighted)
        else:
            avg_delay = None

        n_editions, _weights = await self.get_editions_config()
        editions = list(range(1, int(n_editions) + 1))

        return {
            "series": series,
            "character": character,
            "set_id": set_id,
            "editions": editions,
            "total_generated": total_generated,
            "total_claimed": total_claimed,
            "total_burned": burned_total,
            "total_in_circulation": current_total,
            "claim_rate": claim_rate,
            "avg_claim_time": avg_delay,
            "circ_by_stars": {
                4: circ_by_stars.get(4, 0),
                3: circ_by_stars.get(3, 0),
                2: circ_by_stars.get(2, 0),
                1: circ_by_stars.get(1, 0),
                0: circ_by_stars.get(0, 0),
            },
            "wishlisted": wishlisted,
        }

    async def get_latest_card(self, user_id: int) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("""
                SELECT * FROM cards
                WHERE owned_by=?
                ORDER BY dropped_at DESC
                LIMIT 1
            """, (str(user_id),))
            row = await cur.fetchone()
            if not row:
                return None
            cols = [c[0] for c in cur.description]
            return dict(zip(cols, row))

    # ---------- transactional upgrade ----------
    async def perform_upgrade(
        self,
        user_id: int,
        card_uid: str,
        gold_cost: int,
        dust_quality: str,
        dust_cost: int,
        new_stars: int,
    ) -> bool:
        dust_col = f"dust_{dust_quality}"
        new_condition = QUALITY_BY_STARS.get(int(new_stars), "damaged")

        async with aiosqlite.connect(self.path) as db:
            try:
                await db.execute("BEGIN IMMEDIATE")

                cur = await db.execute("SELECT owned_by, stars FROM cards WHERE card_uid=?", (card_uid,))
                row = await cur.fetchone()
                if not row or row[0] != str(user_id):
                    await db.execute("ROLLBACK")
                    return False

                cur = await db.execute(
                    f"SELECT coins, {dust_col} FROM users WHERE user_id=?",
                    (user_id,)
                )
                urow = await cur.fetchone()
                if not urow:
                    await db.execute("ROLLBACK")
                    return False
                coins, dust_qty = int(urow[0]), int(urow[1])
                if coins < gold_cost or dust_qty < dust_cost:
                    await db.execute("ROLLBACK")
                    return False

                await db.execute(
                    f"UPDATE users SET coins = coins - ?, {dust_col} = {dust_col} - ? WHERE user_id=?",
                    (int(gold_cost), int(dust_cost), user_id)
                )
                await db.execute(
                    "UPDATE cards SET stars=?, condition=? WHERE card_uid=?",
                    (int(new_stars), new_condition, card_uid)
                )

                await db.commit()
                return True
            except Exception:
                await db.execute("ROLLBACK")
                return False
