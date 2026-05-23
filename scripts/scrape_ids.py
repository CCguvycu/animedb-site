"""
AnimeDb scraper -- discovers new MAL IDs from Jikan and merges into api/anime-ids.json.
Designed to find as many unique titles as possible across genres, seasons, and years.
"""
import json, time, datetime, requests
from pathlib import Path

BASE  = "https://api.jikan.moe/v4"
DELAY = 0.5
ROOT  = Path(__file__).parent.parent
OUT   = ROOT / "api" / "anime-ids.json"

# Top-rated: pages 1-30 = up to 750 titles
TOP_PAGES = list(range(1, 31))

# All Jikan genre IDs worth scraping
GENRE_IDS = [
    1,2,4,7,8,9,10,13,14,17,18,19,20,22,23,24,25,27,29,
    30,31,36,37,38,39,40,41,42,43,46,47,48,49,50,51,52,
]

# Seasons going back to 2015
PAST_SEASONS = []
for year in range(2015, 2026):
    for season in ("winter", "spring", "summer", "fall"):
        if year == 2025 and season in ("summer", "fall"):
            continue  # not aired yet
        PAST_SEASONS.append((year, season))

# Search terms that reliably return unique niche titles
SEARCH_TERMS = [
    "manga", "novel", "game", "original", "remake",
    "idol", "sports", "school", "magic", "robot",
    "slice", "battle", "fantasy", "isekai", "romance",
    "horror", "comedy", "drama", "mystery", "history",
]


def build_endpoints():
    eps = []

    # Top-rated (pages 1-30)
    for p in TOP_PAGES:
        eps.append(("/top/anime", {"page": p, "limit": 25}))

    # Top by filter (multiple pages)
    for f in ("airing", "upcoming", "bypopularity", "favorite"):
        for p in range(1, 4):
            eps.append(("/top/anime", {"filter": f, "page": p, "limit": 25}))

    # By type (4 pages each)
    for t in ("tv", "movie", "ova", "special", "music", "ona"):
        for p in range(1, 5):
            eps.append(("/top/anime", {"type": t, "page": p, "limit": 25}))

    # Current + upcoming season (multiple pages)
    eps.append(("/seasons/now", {}))
    eps.append(("/seasons/upcoming", {}))

    # Past seasons (2 pages each for recent years, 1 page for older)
    for year, season in PAST_SEASONS:
        eps.append((f"/seasons/{year}/{season}", {"page": 1}))
        if year >= 2020:
            eps.append((f"/seasons/{year}/{season}", {"page": 2}))
        if year >= 2023:
            eps.append((f"/seasons/{year}/{season}", {"page": 3}))

    # By genre (2 pages each, sorted by score)
    for gid in GENRE_IDS:
        for p in range(1, 3):
            eps.append(("/anime", {"genres": gid, "order_by": "score", "sort": "desc", "page": p, "limit": 25}))
        # also sort by popularity to catch popular-but-lower-rated titles
        eps.append(("/anime", {"genres": gid, "order_by": "members", "sort": "desc", "page": 1, "limit": 25}))

    # Search terms for niche discovery
    for term in SEARCH_TERMS:
        eps.append(("/anime", {"q": term, "order_by": "members", "sort": "desc", "limit": 25}))

    return eps


def fetch(ep, params):
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE}{ep}", params=params, timeout=15)
            if r.status_code == 429:
                wait = 4 * (attempt + 1)
                print(f"    rate-limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            if r.status_code == 404:
                return []
            r.raise_for_status()
            time.sleep(DELAY)
            return r.json().get("data", [])
        except Exception as e:
            print(f"  warn: {ep} -> {e}")
            time.sleep(1)
    return []


def main():
    print("AnimeDb scraper — full discovery run")

    existing = set()
    if OUT.exists():
        with open(OUT) as f:
            existing = set(json.load(f).get("ids", []))
    print(f"  existing: {len(existing)} IDs")

    endpoints = build_endpoints()
    print(f"  endpoints: {len(endpoints)}")

    new_ids = set()
    for i, (ep, params) in enumerate(endpoints, 1):
        items = fetch(ep, params)
        batch = {a["mal_id"] for a in items if a.get("mal_id")}
        new_ids |= batch
        gained = len(new_ids - existing)
        if i % 20 == 0 or i == len(endpoints):
            print(f"  [{i:3d}/{len(endpoints)}] running total new: {gained}")

    all_ids = sorted(existing | new_ids)
    gained  = len(new_ids - existing)

    out = {
        "ids":     all_ids,
        "count":   len(all_ids),
        "updated": datetime.datetime.now(datetime.UTC).isoformat(),
        "source":  "Jikan API v4",
        "endpoints_run": len(endpoints),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f)

    print(f"\n  Done: {len(all_ids)} total IDs (+{gained} new) via {len(endpoints)} endpoints")


if __name__ == "__main__":
    main()
