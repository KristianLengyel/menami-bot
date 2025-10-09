# tools/clear_character_images.py
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "menami.db"

def main():
    db_abs = DB_PATH.resolve()
    print(f"[DB] {db_abs}")

    conn = sqlite3.connect(db_abs)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    # sanity: ensure table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='character_images';")
    if not cur.fetchone():
        print("[ERR] Table 'character_images' not found.")
        conn.close()
        return

    before = cur.execute("SELECT COUNT(*) FROM character_images;").fetchone()[0]
    print(f"[COUNT BEFORE] {before}")

    cur.execute("DELETE FROM character_images;")
    conn.commit()
    conn.close()

    # VACUUM to reclaim space (needs autocommit / fresh connection)
    conn2 = sqlite3.connect(db_abs)
    conn2.isolation_level = None  # autocommit for VACUUM
    conn2.execute("VACUUM;")
    conn2.close()

    # verify
    conn3 = sqlite3.connect(db_abs)
    after = conn3.execute("SELECT COUNT(*) FROM character_images;").fetchone()[0]
    conn3.close()
    print(f"[COUNT AFTER]  {after}")
    print("[DONE] Cleared character_images and vacuumed.")

if __name__ == "__main__":
    main()
