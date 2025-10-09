import os, io, re, json, asyncio, aiohttp, argparse, random
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from PIL import Image

EDITION_COUNT_DEFAULT = 5
OUT_ROOT_DEFAULT = "assets/characters"
CHAR_JSON_DEFAULT = "data/characters.json"
CUT_W, CUT_H = 211, 314
CONCURRENCY = 2
JIKAN_BASE = "https://api.jikan.moe/v4"

def safe_slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w\-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "item"

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def center_crop_to_ratio(img: Image.Image, tgt_w: int, tgt_h: int) -> Image.Image:
    iw, ih = img.size
    target_ratio = tgt_w / tgt_h
    src_ratio = iw / ih
    if src_ratio > target_ratio:
        new_w = int(ih * target_ratio)
        left = (iw - new_w) // 2
        box = (left, 0, left + new_w, ih)
    else:
        new_h = int(iw / target_ratio)
        top = (ih - new_h) // 2
        box = (0, top, iw, top + new_h)
    return img.crop(box).resize((tgt_w, tgt_h), Image.LANCZOS)

def looks_portrait(w: int, h: int, min_ratio: float = 1.05) -> bool:
    return h >= w and (h / max(1, w)) >= min_ratio

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())

def tokens(s: str) -> List[str]:
    return [t for t in re.split(r"[\s\-_/]+", norm(s)) if t]

async def fetch_json(session: aiohttp.ClientSession, url: str, method: str = "GET",
                     json_body: dict = None, retries: int = 5, base_delay: float = 1.5,
                     headers: dict = None):
    for attempt in range(retries):
        try:
            async with session.request(method, url, json=json_body, headers=headers,
                                       timeout=aiohttp.ClientTimeout(total=60)) as r:
                if r.status == 429:
                    delay = base_delay * (attempt + 1) + random.random()
                    print(f"[HTTP 429] {url} sleep {delay:.1f}s")
                    await asyncio.sleep(delay)
                    continue
                if r.status in (500, 502, 503, 504):
                    delay = base_delay * (attempt + 1)
                    print(f"[HTTP {r.status}] {url} retry {delay:.1f}s")
                    await asyncio.sleep(delay)
                    continue
                r.raise_for_status()
                return await r.json()
        except aiohttp.ClientResponseError as e:
            if attempt < retries - 1:
                delay = base_delay * (attempt + 1)
                print(f"[HTTP {e.status}] {url} retry {delay:.1f}s")
                await asyncio.sleep(delay)
                continue
            raise
        except Exception as e:
            if attempt < retries - 1:
                delay = base_delay * (attempt + 1)
                print(f"[ERR] {url} {e} retry {delay:.1f}s")
                await asyncio.sleep(delay)
                continue
            raise
    raise RuntimeError(f"Failed {url} after {retries}")

async def jikan_search_candidates(session: aiohttp.ClientSession, query: str, limit: int = 15):
    url = f"{JIKAN_BASE}/characters?q={aiohttp.helpers.quote(query)}&limit={limit}&order_by=favorites&sort=desc"
    print(f"[Jikan Search] {query}")
    data = await fetch_json(session, url)
    return data.get("data") or []

async def jikan_character_anime_titles(session: aiohttp.ClientSession, mal_id: int) -> List[str]:
    url = f"{JIKAN_BASE}/characters/{mal_id}/anime"
    data = await fetch_json(session, url)
    titles = []
    for a in data.get("data") or []:
        t = a.get("anime", {}).get("title") or ""
        if t:
            titles.append(t)
    return titles

async def jikan_pick_best_character(session: aiohttp.ClientSession, series: str, character: str) -> Optional[dict]:
    char_toks = set(tokens(character))
    series_norm = norm(series)
    cands = await jikan_search_candidates(session, f"{character} {series}", limit=15)
    if not cands:
        cands = await jikan_search_candidates(session, character, limit=15)
        if not cands:
            return None

    scored = []
    for c in cands:
        name = c.get("name") or ""
        n_toks = set(tokens(name))
        tok_match = len(char_toks & n_toks) / max(1, len(char_toks))
        exact_like = 1.0 if norm(name) == norm(character) else 0.0
        score = tok_match * 0.8 + exact_like * 0.2
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [c for c in scored if c[0] >= 0.6][:5] or [scored[0]]

    best = None
    best_score = -1.0
    for score, c in top:
        cid = c.get("mal_id")
        titles = await jikan_character_anime_titles(session, cid)
        in_series = any(series_norm in norm(t) for t in titles)
        final_score = score + (0.3 if in_series else 0.0)
        print(f"[Pick] cand id={cid} name={c.get('name')} tok_score={score:.2f} in_series={in_series}")
        if final_score > best_score:
            best_score = final_score
            best = c
    if best:
        print(f"[Chosen] id={best.get('mal_id')} name={best.get('name')} score={best_score:.2f}")
    return best

async def jikan_pictures(session: aiohttp.ClientSession, mal_id: int) -> List[str]:
    url = f"{JIKAN_BASE}/characters/{mal_id}/pictures"
    data = await fetch_json(session, url)
    out = []
    for p in data.get("data") or []:
        img = (p.get("jpg") or {}).get("image_url")
        if img:
            out.append(img)
    print(f"[Pics] {mal_id} {len(out)}")
    return out

async def head_size(session: aiohttp.ClientSession, url: str) -> Tuple[int,int]:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=40)) as r:
            r.raise_for_status()
            b = await r.read()
        im = Image.open(io.BytesIO(b))
        return im.width, im.height
    except Exception:
        return (0, 0)

async def download_image(session: aiohttp.ClientSession, url: str) -> Optional[Image.Image]:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=40)) as r:
            r.raise_for_status()
            b = await r.read()
        im = Image.open(io.BytesIO(b)).convert("RGBA")
        return im
    except Exception as e:
        print(f"[Download ERR] {url} {e}")
        return None

async def collect_urls(session: aiohttp.ClientSession, series: str, character: str, want: int) -> List[str]:
    urls: List[str] = []
    best = await jikan_pick_best_character(session, series, character)
    if best:
        cid = best.get("mal_id")
        urls += await jikan_pictures(session, cid)
    portrait: List[str] = []
    for u in urls:
        w, h = await head_size(session, u)
        if w and h:
            print(f"[Probe] {w}x{h} {u}")
        if w and h and looks_portrait(w, h, 1.02):
            portrait.append(u)
    if not portrait:
        portrait = urls
    dedup = []
    for u in portrait:
        if u not in dedup:
            dedup.append(u)
    print(f"[Collect] {min(len(dedup), want)} / {want}")
    return dedup[:want]

def existing_editions(folder: Path, editions: int) -> List[Optional[Path]]:
    out: List[Optional[Path]] = []
    for i in range(1, editions+1):
        p_png = folder / f"ed{i}.png"
        p_jpg = folder / f"ed{i}.jpg"
        p_jpeg = folder / f"ed{i}.jpeg"
        if p_png.exists(): out.append(p_png)
        elif p_jpg.exists(): out.append(p_jpg)
        elif p_jpeg.exists(): out.append(p_jpeg)
        else: out.append(None)
    return out

async def process_one_character(sem: asyncio.Semaphore, session: aiohttp.ClientSession,
                                out_root: Path, series: str, character: str,
                                editions: int, overwrite: bool) -> Tuple[str, str, List[Path]]:
    async with sem:
        print(f"\n[Start] {series} | {character}")
        series_slug = safe_slug(series)
        char_slug = safe_slug(character)
        folder = out_root / series_slug / char_slug
        ensure_dir(folder)
        slots = existing_editions(folder, editions)
        if not overwrite and all(p is not None for p in slots):
            print("[Skip] already has all editions")
            return (series, character, [p for p in slots if p is not None])
        try:
            urls = await collect_urls(session, series, character, editions)
        except Exception as e:
            print(f"[Collect ERR] {series} | {character} -> {e}")
            urls = []
        saved: List[Path] = []
        url_idx = 0
        for i in range(1, editions+1):
            existing = slots[i-1]
            if existing is not None and not overwrite:
                saved.append(existing)
                print(f"[Keep] ed{i} {existing.name}")
                continue
            u = urls[url_idx] if url_idx < len(urls) else None
            if u:
                im = await download_image(session, u)
                if im:
                    iw, ih = im.size
                    print(f"[Image] src {iw}x{ih}")
                    im = center_crop_to_ratio(im, CUT_W, CUT_H)
                    print(f"[Image] cropped {CUT_W}x{CUT_H}")
                    dest = folder / f"ed{i}.png"
                    im.save(dest)
                    print(f"[Save] {dest}")
                    saved.append(dest)
                    url_idx += 1
                    continue
            if existing is not None:
                saved.append(existing)
            else:
                placeholder = Image.new("RGBA", (CUT_W, CUT_H), (200, 200, 200, 255))
                dest = folder / f"ed{i}.png"
                placeholder.save(dest)
                print(f"[Placeholder] {dest}")
                saved.append(dest)
        print(f"[Done] {series} | {character} total {len(saved)}")
        return (series, character, saved)

def print_mimgset(series: str, character: str, paths: List[Path]):
    print(f"\n[MIMGSET] {series} · {character}")
    for idx, p in enumerate(paths, 1):
        print(f'mimgset "{series}" "{character}" {idx} file://{p.resolve()}')

async def seed_db_for_character(series: str, character: str, paths: List[Path]) -> None:
    return

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--characters", default=CHAR_JSON_DEFAULT)
    parser.add_argument("--out", default=OUT_ROOT_DEFAULT)
    parser.add_argument("--editions", type=int, default=EDITION_COUNT_DEFAULT)
    parser.add_argument("--series", nargs="*")
    parser.add_argument("--seeddb", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    out_root = Path(args.out)
    ensure_dir(out_root)
    with open(args.characters, "r", encoding="utf-8") as f:
        mapping: Dict[str, List[str]] = json.load(f)
    if args.series:
        mapping = {k: v for k, v in mapping.items() if k in args.series}
    sem = asyncio.Semaphore(CONCURRENCY)
    timeout = aiohttp.ClientTimeout(total=60)
    conn = aiohttp.TCPConnector(limit=CONCURRENCY)
    async with aiohttp.ClientSession(timeout=timeout, connector=conn) as session:
        tasks = []
        for series, chars in mapping.items():
            for character in chars:
                tasks.append(process_one_character(sem, session, out_root, series, character,
                                                   args.editions, args.overwrite))
        results: List[Tuple[str, str, List[Path]]] = []
        for chunk in [tasks[i:i+20] for i in range(0, len(tasks), 20)]:
            results += await asyncio.gather(*chunk)
            await asyncio.sleep(2.0)
    for series, character, paths in results:
        print_mimgset(series, character, paths)
        if args.seeddb:
            await seed_db_for_character(series, character, paths)

if __name__ == "__main__":
    asyncio.run(main())
