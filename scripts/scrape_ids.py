"""
AnimeDb scraper -- parallel discovery via ThreadPoolExecutor + requests.
3 threads saturates Jikan's 3 req/s limit without burst 429s.
"""
import json, time, datetime, sys, threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

BASE   = "https://api.jikan.moe/v4"
ROOT   = Path(__file__).parent.parent
OUT    = ROOT / "api" / "anime-ids.json"
WORKERS = 3
DELAY   = 0.35   # per-thread delay — 3 threads × 0.35s ≈ ~1 req/0.35s burst window

_lock   = threading.Lock()
_done   = [0]
_total  = [0]
_found  = [0]


def build_endpoints():
    eps = []

    for p in range(1, 31):
        eps.append(("/top/anime", {"page": p, "limit": 25}))

    for f in ("airing", "upcoming", "bypopularity", "favorite"):
        for p in range(1, 4):
            eps.append(("/top/anime", {"filter": f, "page": p, "limit": 25}))

    for t in ("tv", "movie", "ova", "special", "music", "ona"):
        for p in range(1, 5):
            eps.append(("/top/anime", {"type": t, "page": p, "limit": 25}))

    eps.append(("/seasons/now", {}))
    eps.append(("/seasons/upcoming", {}))

    for year in range(2015, 2026):
        for season in ("winter", "spring", "summer", "fall"):
            if year == 2025 and season in ("summer", "fall"):
                continue
            eps.append((f"/seasons/{year}/{season}", {"page": 1}))
            if year >= 2020:
                eps.append((f"/seasons/{year}/{season}", {"page": 2}))
            if year >= 2023:
                eps.append((f"/seasons/{year}/{season}", {"page": 3}))

    genre_ids = [
        1,2,4,7,8,9,10,13,14,17,18,19,20,22,23,24,25,27,29,
        30,31,36,37,38,39,40,41,42,43,46,47,48,49,50,51,52,
    ]
    for gid in genre_ids:
        for p in range(1, 3):
            eps.append(("/anime", {"genres": gid, "order_by": "score",   "sort": "desc", "page": p, "limit": 25}))
        eps.append(("/anime",     {"genres": gid, "order_by": "members", "sort": "desc", "page": 1, "limit": 25}))

    for term in ["manga","novel","game","original","remake","idol","sports","school",
                 "magic","robot","slice","battle","fantasy","isekai","romance",
                 "horror","comedy","drama","mystery","history"]:
        eps.append(("/anime", {"q": term, "order_by": "members", "sort": "desc", "limit": 25}))

    return eps


def fetch_one(ep, params, session, existing):
    time.sleep(DELAY)
    url = f"{BASE}{ep}"
    for attempt in range(3):
        try:
            r = session.get(url, params=params, timeout=12)
            if r.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            if r.status_code == 404:
                return set()
            r.raise_for_status()
            data = r.json().get("data", [])
            ids  = {a["mal_id"] for a in data if a.get("mal_id")}
            new  = ids - existing
            with _lock:
                _done[0]  += 1
                _found[0] += len(new)
                done = _done[0]
                if done % 50 == 0 or done == _total[0]:
                    print(f"  [{done:3d}/{_total[0]}] +{_found[0]} new IDs found")
            return ids
        except Exception as e:
            time.sleep(1 * (attempt + 1))
    with _lock:
        _done[0] += 1
    return set()


def main():
    print("AnimeDb — parallel scraper (3 threads)")

    existing = set()
    if OUT.exists():
        with open(OUT) as f:
            existing = set(json.load(f).get("ids", []))
    print(f"  existing : {len(existing)} IDs")

    endpoints = build_endpoints()
    _total[0] = len(endpoints)
    print(f"  endpoints: {len(endpoints)}")
    print(f"  workers  : {WORKERS} threads")

    t0 = time.time()
    all_new = set()

    session = requests.Session()
    session.headers.update({"User-Agent": "AnimeDb-Scraper/2.0"})

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(fetch_one, ep, params, session, existing): (ep, params)
                   for ep, params in endpoints}
        for fut in as_completed(futures):
            result = fut.result()
            all_new.update(result)

    elapsed = time.time() - t0
    all_ids = sorted(existing | all_new)
    gained  = len(all_new - existing)

    out = {
        "ids":           all_ids,
        "count":         len(all_ids),
        "updated":       datetime.datetime.now(datetime.UTC).isoformat(),
        "source":        "Jikan API v4",
        "endpoints_run": len(endpoints),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f)

    print(f"\n  Done in {elapsed:.0f}s")
    print(f"  {len(all_ids)} total IDs  (+{gained} new)  via {len(endpoints)} endpoints")


if __name__ == "__main__":
    main()
