# tools/apply_imgset.py
from __future__ import annotations
import os, sys, argparse, pathlib, re, json, shlex, subprocess, sqlite3
from datetime import datetime, timezone
from typing import List, Tuple, Dict
from PIL import Image
from supabase import create_client, Client

BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
ASSETS = BASE_DIR / "assets" / "characters"
CHAR_FILE = BASE_DIR / "characters.json"
DB_PATH = BASE_DIR / "menami.db"

# ====== Supabase config from environment ======
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "cards").strip()

def require_supabase():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("[ERROR] Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables.")
        sys.exit(1)

def supa_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# ====== Helpers ======
def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w\s\-\.]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s

def load_char_index() -> Dict[Tuple[str, str], Tuple[str, str]]:
    if not CHAR_FILE.exists():
        return {}
    try:
        data = json.loads(CHAR_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    idx: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for series, chars in data.items():
        sslug = slugify(series)
        for ch in chars:
            cslug = slugify(ch)
            idx[(sslug, cslug)] = (series, ch)
    return idx

def iter_character_editions(series_filter: str | None = None,
                            char_filter: str | None = None):
    idx = load_char_index()
    if not ASSETS.exists():
        return
    for series_dir in sorted(p for p in ASSETS.iterdir() if p.is_dir()):
        sslug = series_dir.name
        for char_dir in sorted(p for p in series_dir.iterdir() if p.is_dir()):
            cslug = char_dir.name
            series_name, char_name = idx.get(
                (sslug, cslug),
                (series_dir.name.replace("_"," ").title(), char_dir.name.replace("_"," ").title()),
            )
            if series_filter and series_filter.lower() != series_name.lower():
                continue
            if char_filter and char_filter.lower() != char_name.lower():
                continue
            eds: List[Tuple[int, pathlib.Path]] = []
            for ed in range(1, 6):
                fp = char_dir / f"ed{ed}.png"
                if fp.exists():
                    eds.append((ed, fp))
            if eds:
                yield series_name, char_name, eds

def build_job(series: str, character: str, ed: int, fp: pathlib.Path) -> dict:
    abs_path = fp.resolve()
    return {"series": series, "character": character, "edition": ed, "path": abs_path}

def ensure_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS character_images (
            series TEXT NOT NULL,
            character TEXT NOT NULL,
            set_id INTEGER NOT NULL,
            image_url TEXT NOT NULL,
            bytes INTEGER,
            mime TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (series, character, set_id)
        )
        """)
        conn.commit()

def upsert_character_image(series: str, character: str, set_id: int,
                           image_url: str, size: int | None, mime: str | None):
    ts = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO character_images(series, character, set_id, image_url, bytes, mime, updated_at)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(series, character, set_id)
            DO UPDATE SET image_url=excluded.image_url,
                          bytes=excluded.bytes,
                          mime=excluded.mime,
                          updated_at=excluded.updated_at
        """, (series, character, int(set_id), image_url, size, mime, ts))
        conn.commit()

# ====== Supabase upload ======
def public_url_for(path: str) -> str:
    # For public buckets, this yields a stable URL
    return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{path}"

def ensure_bucket_exists(supa: Client, bucket: str, public: bool = True):
    # Try to fetch; if not found, create via API (recommended approach). :contentReference[oaicite:2]{index=2}
    try:
        _ = supa.storage.get_bucket(bucket)
        print(f"[BUCKET] Using existing bucket '{bucket}'")
    except Exception:
        print(f"[BUCKET] Creating bucket '{bucket}' (public={public})")
        # supabase-py v2 signature uses options dict
        supa.storage.create_bucket(bucket, options={"public": public})
        print(f"[BUCKET] Created '{bucket}'")

def upload_one_image_to_supabase(supa: Client, local_path: pathlib.Path,
                                 dest_path: str, content_type: str = "image/png") -> tuple[str, int, str]:
    data = local_path.read_bytes()
    size = len(data)
    # upsert=True so reruns replace the same object
    supa.storage.from_(SUPABASE_BUCKET).upload(
        dest_path, data, file_options={"contentType": content_type, "upsert": "true"}
    )
    url = public_url_for(dest_path)
    return url, size, content_type

def run_supabase_uploader(jobs: List[dict]) -> int:
    require_supabase()
    supa = supa_client()
    ensure_bucket_exists(supa, SUPABASE_BUCKET, public=True)
    uploaded = 0

    for j in jobs:
        series = j["series"]; character = j["character"]; ed = j["edition"]; p: pathlib.Path = j["path"]
        # Storage path: <series_slug>/<char_slug>/ed#.png
        series_slug = slugify(series)
        char_slug = slugify(character)
        dest = f"{series_slug}/{char_slug}/ed{ed}.png"

        try:
            with Image.open(p) as im:
                w, h = im.size
            print(f'[UPLOAD] {series} · {character} · ◈{ed} -> "{p.name}" {w}x{h}')
        except Exception as e:
            print(f"[SKIP] {p} -> {e}")
            continue

        try:
            url, size, mime = upload_one_image_to_supabase(supa, p, dest, "image/png")
            print(f"  [OK] {url}")
            upsert_character_image(series, character, ed, url, size, mime)
            uploaded += 1
        except Exception as e:
            print(f"  [ERR] upload failed -> {e}")

    return uploaded

# ====== Optional shell runner (unchanged) ======
def run_shell(commands):
    for cmd in commands:
        try:
            if os.name == "nt":
                subprocess = __import__("subprocess")
                subprocess.run(cmd, shell=True, check=True)
            else:
                subprocess = __import__("subprocess"); shlex_local = __import__("shlex")
                subprocess.run(shlex_local.split(cmd), check=True)
        except Exception as e:
            print(f"[SHELL ERROR] {cmd} -> {e}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", choices=["print","shell","supabase"], default="print")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--series", help="only this series name (case-insensitive)")
    ap.add_argument("--character", help="only this character name (case-insensitive)")
    args = ap.parse_args()

    jobs: List[dict] = []
    count = 0
    for series, character, eds in iter_character_editions(args.series, args.character):
        print(f"[MIMGSET] {series} · {character}")
        for ed, fp in eds:
            job = build_job(series, character, ed, fp)
            jobs.append(job)
            print(f'mimgset {ed} {series} | {character}    ({job["path"]})')
            count += 1
            if args.limit and count >= args.limit:
                break
        if args.limit and count >= args.limit:
            break

    if not jobs:
        print("[INFO] No editions found to apply.")
        return

    if args.apply == "print":
        return

    if args.apply == "shell":
        cmds = [f'mimgset {j["edition"]} {j["series"]} | {j["character"]} {j["path"]}' for j in jobs]
        run_shell(cmds)
        return

    if args.apply == "supabase":
        ensure_db()
        db_abs = DB_PATH.resolve()
        print(f"[DB] Using {db_abs}")

        with sqlite3.connect(DB_PATH) as conn:
            before_cnt = conn.execute("SELECT COUNT(*) FROM character_images").fetchone()[0]

        wrote = run_supabase_uploader(jobs)

        with sqlite3.connect(DB_PATH) as conn:
            after_cnt = conn.execute("SELECT COUNT(*) FROM character_images").fetchone()[0]

        print(f"[DONE] Upserted {wrote} rows into {db_abs}")
        print(f"[COUNT] character_images: {before_cnt} -> {after_cnt}")
        return

if __name__ == "__main__":
    main()
