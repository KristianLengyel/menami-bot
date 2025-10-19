# tools/clear_user_dyes.py
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
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_dyes';")
    if not cur.fetchone():
        print("[ERR] Table 'user_dyes' not found.")
        conn.close()
        return

    before = cur.execute("SELECT COUNT(*) FROM user_dyes;").fetchone()[0]
    print(f"[COUNT BEFORE] {before}")

    cur.execute("DELETE FROM user_dyes;")
    conn.commit()
    conn.close()

    # VACUUM to reclaim space (needs autocommit / fresh connection)
    conn2 = sqlite3.connect(db_abs)
    conn2.isolation_level = None  # autocommit for VACUUM
    conn2.execute("VACUUM;")
    conn2.close()

    # reset AUTOINCREMENT counter
    conn3 = sqlite3.connect(db_abs)
    conn3.execute("DELETE FROM sqlite_sequence WHERE name='user_dyes';")
    conn3.commit()
    after = conn3.execute("SELECT COUNT(*) FROM user_dyes;").fetchone()[0]
    conn3.close()

    print(f"[COUNT AFTER]  {after}")
    print("[DONE] Cleared user_dyes, reset sequence, and vacuumed.")

if __name__ == "__main__":
    main()
