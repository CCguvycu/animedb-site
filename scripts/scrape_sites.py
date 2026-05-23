"""
AnimeDb site discovery -- checks a master list of anime streaming sites,
verifies which are live via HEAD requests, merges into api/sites.json.
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

ROOT    = Path(__file__).parent.parent
OUT     = ROOT / "api" / "sites.json"
WORKERS = 12
TIMEOUT = 6

# ── Master site list ───────────────────────────────────────────────────────────
# Format: (name, url, tag)
# tag: sub | dub | both | official | manga
MASTER = [
    # ── Sub ──────────────────────────────────────────────────────────────────
    ("HiAnime",          "https://hianime.to/",                 "sub",      True),
    ("Miruro",           "https://www.miruro.tv/",              "sub",      True),
    ("AnimePahe",        "https://animepahe.ru/",               "sub",      True),
    ("Aniwave",          "https://aniwave.to/",                 "sub",      False),
    ("Tenshi",           "https://tenshi.moe/",                 "sub",      False),
    ("KickAssAnime",     "https://kickassanime.mx/",            "sub",      False),
    ("AniZone",          "https://anizone.to/",                 "sub",      False),
    ("Anistream",        "https://anistream.xyz/",              "sub",      False),
    ("AniKuro",          "https://anikuro.com/",                "sub",      False),
    ("AnimeParadise",    "https://animeparadise.moe/",          "sub",      False),
    ("Kaido",            "https://kaido.to/",                   "sub",      False),
    ("AnimeHeaven",      "https://animeheaven.me/",             "sub",      False),
    ("AnimeOnsen",       "https://www.animeonsen.xyz/",         "sub",      False),
    ("Marin",            "https://marin.moe/",                  "sub",      False),
    ("Twist",            "https://twist.moe/",                  "sub",      False),
    ("AnimeRush",        "https://www.animerush.tv/",           "sub",      False),
    ("GogoAnime",        "https://gogoanime.by/",               "sub",      False),
    ("AnimeSuge",        "https://animesuge.to/",               "sub",      False),
    ("AnimeXin",         "https://animexin.xyz/",               "sub",      False),
    ("AniPlay",          "https://aniplay.co/",                 "sub",      False),
    ("AniFast",          "https://anifast.com/",                "sub",      False),
    ("Kaguya",           "https://kaguya.app/",                 "sub",      False),
    ("AniWorld",         "https://aniworld.to/",                "sub",      False),
    ("Aniakuma",         "https://aniakuma.net/",               "sub",      False),
    ("AnimeDao",         "https://animedao.to/",                "sub",      False),
    ("AnimeSaturn",      "https://www.animesaturn.cx/",         "sub",      False),
    ("WitAnime",         "https://witanime.cyou/",              "sub",      False),
    ("AniVibe",          "https://anivibe.net/",                "sub",      False),
    ("AniMixPlay",       "https://animixplay.to/",              "sub",      False),
    ("Neko",             "https://neko-sama.fr/",               "sub",      False),
    ("Anime-sama",       "https://anime-sama.fr/",              "sub",      False),
    ("AnimeVF",          "https://www.animevf.co/",             "sub",      False),
    ("VoirAnime",        "https://www.voiranime.art/",          "sub",      False),
    ("AnimeUltime",      "https://www.animeultime.net/",        "sub",      False),
    ("YugenAnime",       "https://yugenanime.sx/",              "sub",      False),
    ("AnimeKhor",        "https://animekhor.xyz/",              "sub",      False),
    ("AnimeBlkom",       "https://animeblkom.net/",             "sub",      False),
    ("ShaaLa",           "https://shaala.top/",                 "sub",      False),
    ("AnimeLak",         "https://animelak.net/",               "sub",      False),
    ("AniPlay.TV",       "https://aniplay.tv/",                 "sub",      False),
    ("9Anime",           "https://9animetv.to/",                "sub",      False),
    ("AnimeFlix",        "https://animeflix.io/",               "sub",      False),
    ("AnimeRealm",       "https://animerealm.pro/",             "sub",      False),
    # ── Dub ──────────────────────────────────────────────────────────────────
    ("Funimation",       "https://www.funimation.com/",         "dub",      False),
    ("DubHappy",         "https://dubhappy.me/",                "dub",      False),
    ("GogoAnimeDub",     "https://www.gogoanime3.co/",          "dub",      False),
    ("AnimeLand",        "https://www.animeland.us/",           "dub",      False),
    ("AnimeOwl",         "https://animeowl.me/",                "dub",      False),
    ("DubbedAnime",      "https://dubbedanime.net/",            "dub",      False),
    ("AnimeGlare",       "https://animeglare.xyz/",             "dub",      False),
    ("DubbedAnimeHQ",    "https://dubbedanime.io/",             "dub",      False),
    # ── Sub + Dub ─────────────────────────────────────────────────────────────
    ("Animetsu",         "https://animetsu.cc/home",            "both",     True),
    ("AnimeLok",         "https://animelok.online/home",        "both",     True),
    ("Rive",             "https://rivestream.live/",            "both",     True),
    ("AniZone.tv",       "https://anizone.tv/",                 "both",     False),
    ("Aniwatch",         "https://aniwatch.to/",                "both",     False),
    ("Zoro",             "https://zoroanime.pro/",              "both",     False),
    ("AllAnime",         "https://allanime.to/",                "both",     False),
    ("AnimeKai",         "https://animekai.to/",                "both",     False),
    ("AnimeQ",           "https://animeq.to/",                  "both",     False),
    ("AnimeUniverse",    "https://animeuniverse.to/",           "both",     False),
    ("AnimeGG",          "https://animegg.org/",                "both",     False),
    ("WcoStream",        "https://www.wcostream.tv/",           "both",     False),
    ("WcoAnime",         "https://www.wcofun.net/",             "both",     False),
    ("4Anime",           "https://4anime.gg/",                  "both",     False),
    ("AnimeVibe",        "https://animevibe.to/",               "both",     False),
    ("Aniplot",          "https://aniplot.com/",                "both",     False),
    ("AnimeFreak",       "https://animefreak.tv/",              "both",     False),
    ("ToonamiAftermath", "https://www.toonamiaftermath.com/",   "both",     False),
    ("AnimeSee",         "https://animesee.org/",               "both",     False),
    ("Anilinkz",         "https://anilinkz.to/",                "both",     False),
    ("Animension",       "https://animension.to/",              "both",     False),
    ("AnimeFever",       "https://www.animefever.cc/",          "both",     False),
    ("AnimeHub",         "https://animehub.ac/",                "both",     False),
    ("Kayoanime",        "https://kayoanime.com/",              "both",     False),
    ("AnimeDekho",       "https://animedekho.com/",             "both",     False),
    ("AnimeStream",      "https://animestream.in/",             "both",     False),
    ("AnimeFlix.tv",     "https://animeflix.tv/",               "both",     False),
    ("AnimeWave",        "https://animewave.net/",              "both",     False),
    ("AnimeKing",        "https://animaking.to/",               "both",     False),
    ("AnimeXcel",        "https://animexcel.net/",              "both",     False),
    # ── Official ──────────────────────────────────────────────────────────────
    ("Crunchyroll",      "https://www.crunchyroll.com/",        "official", True),
    ("Netflix",          "https://www.netflix.com/",            "official", True),
    ("HiDive",           "https://www.hidive.com/",             "official", False),
    ("Amazon Prime",     "https://www.primevideo.com/",         "official", False),
    ("Disney+",          "https://www.disneyplus.com/",         "official", False),
    ("Hulu",             "https://www.hulu.com/",               "official", False),
    ("Apple TV+",        "https://tv.apple.com/",               "official", False),
    ("Tubi",             "https://tubitv.com/",                 "official", False),
    ("RetroCrush",       "https://www.retrocrush.tv/",          "official", False),
    ("Pluto TV",         "https://pluto.tv/",                   "official", False),
    ("AnimeDigitalNetwork","https://animedigitalnetwork.com/",  "official", False),
    ("BiliBili",         "https://www.bilibili.tv/",            "official", False),
    ("Muse Asia",        "https://www.youtube.com/@MuseAsia",   "official", False),
    # ── Manga ─────────────────────────────────────────────────────────────────
    ("MangaDex",         "https://mangadex.org/",               "manga",    True),
    ("MangaPlus",        "https://mangaplus.shueisha.co.jp/",   "manga",    True),
    ("MangaSee",         "https://mangasee123.com/",            "manga",    True),
    ("MangaFire",        "https://mangafire.to/",               "manga",    True),
    ("MangaKakalot",     "https://mangakakalot.com/",           "manga",    False),
    ("MangaBuddy",       "https://mangabuddy.com/",             "manga",    False),
    ("MangaReader",      "https://mangareader.to/",             "manga",    False),
    ("TCBScans",         "https://tcbscans.me/",                "manga",    False),
    ("WeebCentral",      "https://weebcentral.com/",            "manga",    False),
    ("ComicK",           "https://comick.io/",                  "manga",    False),
    ("MangaFox",         "https://fanfox.net/",                 "manga",    False),
    ("MangaNelo",        "https://chapmanganelo.com/",          "manga",    False),
    ("Bato.to",          "https://bato.to/",                    "manga",    False),
    ("MangaOwl",         "https://mangaowl.io/",                "manga",    False),
    ("MangaHere",        "https://www.mangahere.cc/",           "manga",    False),
    ("MangaStream",      "https://readmng.com/",                "manga",    False),
]

_lock  = threading.Lock()
_done  = [0]
_alive = [0]


def check_site(entry, session):
    name, url, tag, top = entry
    try:
        r = session.head(url, timeout=TIMEOUT, allow_redirects=True)
        live = r.status_code < 500
    except Exception:
        live = False

    with _lock:
        _done[0] += 1
        if live:
            _alive[0] += 1
        if _done[0] % 20 == 0 or _done[0] == len(MASTER):
            print(f"  [{_done[0]:3d}/{len(MASTER)}] {_alive[0]} live so far")

    return (name, url, tag, top, live)


def main():
    print("AnimeDb site discovery")
    print(f"  checking {len(MASTER)} sites with {WORKERS} workers")

    # Load existing sites for merging
    existing = {}
    if OUT.exists():
        with open(OUT) as f:
            data = json.load(f)
        for s in data.get("sites", []):
            existing[s["url"].rstrip("/")] = s

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 AnimeDb/2.0"})

    t0 = time.time()
    results = []

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(check_site, entry, session): entry for entry in MASTER}
        for fut in as_completed(futures):
            results.append(fut.result())

    elapsed = time.time() - t0

    # Build site list: live sites only, merge with existing metadata
    sites = []
    seen_urls = set()
    for name, url, tag, top, live in results:
        if not live:
            continue
        key = url.rstrip("/")
        if key in seen_urls:
            continue
        seen_urls.add(key)

        # Preserve any extra metadata from existing record
        existing_rec = existing.get(key, {})
        site = {"name": name, "url": url, "tag": tag}
        if top:
            site["top"] = True
        sites.append(site)

    # Sort: top picks first, then alphabetical within tag
    tag_order = {"sub": 0, "both": 1, "dub": 2, "official": 3, "manga": 4}
    sites.sort(key=lambda s: (tag_order.get(s["tag"], 9), not s.get("top", False), s["name"].lower()))

    counts = {}
    for s in sites:
        counts[s["tag"]] = counts.get(s["tag"], 0) + 1

    out = {
        "sites":      sites,
        "count":      len(sites),
        "updated":    datetime.datetime.now(datetime.UTC).isoformat(),
        "categories": counts,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"\n  Done in {elapsed:.0f}s")
    print(f"  {len(sites)}/{len(MASTER)} sites live — {counts}")


if __name__ == "__main__":
    main()
