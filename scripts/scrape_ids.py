"""
Jikan scraper -- fetches MAL IDs and merges into api/anime-ids.json.
Runs locally and as a GitHub Action (weekly cron).
"""
import json, time, datetime, requests
from pathlib import Path

BASE  = "https://api.jikan.moe/v4"
DELAY = 0.5
ROOT  = Path(__file__).parent.parent
OUT   = ROOT / "api" / "anime-ids.json"

TOP_PAGES = list(range(1, 21))

GENRE_IDS = [1,2,4,7,8,9,10,14,18,19,22,23,24,25,27,29,36,37,41]

PAST_SEASONS = [
    (2025,"winter"),(2025,"spring"),
    (2024,"winter"),(2024,"spring"),(2024,"summer"),(2024,"fall"),
    (2023,"winter"),(2023,"spring"),(2023,"summer"),(2023,"fall"),
    (2022,"winter"),(2022,"spring"),(2022,"summer"),(2022,"fall"),
    (2021,"winter"),(2021,"spring"),(2021,"summer"),(2021,"fall"),
    (2020,"winter"),(2020,"spring"),(2020,"summer"),(2020,"fall"),
]


def build_endpoints():
    eps = []
    for p in TOP_PAGES:
        eps.append(("/top/anime", {"page": p, "limit": 25}))
    for f in ("airing", "upcoming", "bypopularity", "favorite"):
        eps.append(("/top/anime", {"filter": f, "limit": 25}))
    for t in ("movie", "ova", "special", "music"):
        for p in range(1, 5):
            eps.append(("/top/anime", {"type": t, "page": p, "limit": 25}))
    eps.append(("/seasons/now", {}))
    eps.append(("/seasons/upcoming", {}))
    for year, season in PAST_SEASONS:
        eps.append((f"/seasons/{year}/{season}", {}))
    for gid in GENRE_IDS:
        eps.append(("/anime", {"genres": gid, "order_by": "score", "sort": "desc", "limit": 25}))
    return eps


def fetch(ep, params):
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE}{ep}", params=params, timeout=15)
            if r.status_code == 429:
                wait = 3 * (attempt + 1)
                print(f"    rate-limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            time.sleep(DELAY)
            return r.json().get("data", [])
        except Exception as e:
            print(f"  warn: {ep} -> {e}")
            time.sleep(1)
    return []


def main():
    print("AnimeDb scraper")
    existing = set()
    if OUT.exists():
        with open(OUT) as f:
            existing = set(json.load(f).get("ids", []))
    print(f"  existing: {len(existing)} IDs")

    endpoints = build_endpoints()
    new_ids = set()
    for i, (ep, params) in enumerate(endpoints, 1):
        items = fetch(ep, params)
        batch = {a["mal_id"] for a in items if a.get("mal_id")}
        new_ids |= batch
        print(f"  [{i:3d}/{len(endpoints)}] {ep} -> {len(batch)} | new so far: {len(new_ids - existing)}")

    all_ids = sorted(existing | new_ids)
    gained  = len(new_ids - existing)

    out = {
        "ids":     all_ids,
        "count":   len(all_ids),
        "updated": datetime.datetime.now(datetime.UTC).isoformat(),
        "source":  "Jikan API v4",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f)

    print(f"\n  Done: {len(all_ids)} total IDs (+{gained} new)")


if __name__ == "__main__":
    main()
