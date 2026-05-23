"""
Sync api/anime-ids.json from animedb-site → anistream-site/data/anime-ids.json
Run after scrape_ids.py. Requires GH_PAT env var (public_repo scope).
"""
import json, os, sys, base64
from pathlib import Path

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

PAT      = os.environ.get("GH_PAT", "")
SRC      = Path(__file__).parent.parent / "api" / "anime-ids.json"
AW_REPO  = "CCguvycu/anistream-site"
AW_PATH  = "data/anime-ids.json"
GH_API   = "https://api.github.com"

def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)

if not PAT:
    die("GH_PAT env var not set — add it as a repo secret")

headers = {
    "Authorization": f"Bearer {PAT}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# 1. Load local source
src_data = json.loads(SRC.read_text(encoding="utf-8"))
src_ids  = src_data["ids"]
print(f"Source: {len(src_ids):,} IDs from api/anime-ids.json")

# 2. Get current AnimeWeb file (for SHA + existing IDs)
url = f"{GH_API}/repos/{AW_REPO}/contents/{AW_PATH}"
res = requests.get(url, headers=headers, timeout=20)

sha          = None
existing_ids = []

if res.status_code == 200:
    fd           = res.json()
    sha          = fd["sha"]
    raw_content  = base64.b64decode(fd["content"].replace("\n", "")).decode("utf-8")
    try:
        existing_ids = json.loads(raw_content).get("ids", [])
    except Exception:
        pass
    print(f"AnimeWeb: {len(existing_ids):,} existing IDs (sha {sha[:7]})")
elif res.status_code == 404:
    print("AnimeWeb: data/anime-ids.json not found — will create")
else:
    die(f"GET failed: {res.status_code} {res.json().get('message','')}")

# 3. Merge and check delta
merged     = sorted(set(existing_ids) | set(src_ids))
added      = len(merged) - len(existing_ids)

if added == 0:
    print("AnimeWeb already up to date — nothing to push")
    sys.exit(0)

print(f"Merging: +{added} new IDs → {len(merged):,} total")

# 4. Encode and PUT
out = {
    "ids":     merged,
    "count":   len(merged),
    "updated": src_data.get("updated", ""),
    "source":  "animedb-auto-sync",
}
encoded = base64.b64encode(json.dumps(out, indent=2).encode("utf-8")).decode("ascii")

body = {
    "message": f"chore: auto-sync {added} IDs from AnimeDb [skip ci]",
    "content": encoded,
}
if sha:
    body["sha"] = sha

put = requests.put(url, headers=headers, json=body, timeout=30)

if put.status_code in (200, 201):
    commit_sha = put.json()["commit"]["sha"][:7]
    print(f"Pushed {added} IDs to AnimeWeb — commit {commit_sha}")
    print(f"AnimeWeb catalog: {len(merged):,} IDs")
else:
    die(f"PUT failed: {put.status_code} {put.json().get('message','')}")
