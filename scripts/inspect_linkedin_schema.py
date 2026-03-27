#!/usr/bin/env python3
"""Inspect the raw schema from apimaestro/linkedin-profile-posts."""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from config.settings import settings

TOKEN = settings.APIFY_API_TOKEN
ACTOR = "apimaestro~linkedin-profile-posts"
BASE = "https://api.apify.com/v2"

# Start run
r = requests.post(
    f"{BASE}/acts/{ACTOR}/runs",
    json={"profileUrl": "https://www.linkedin.com/in/satyanadella/", "maxPosts": 10},
    params={"token": TOKEN}, timeout=20,
)
run_id = r.json()["data"]["id"]
print(f"Run: {run_id}")

# Poll
for _ in range(20):
    time.sleep(6)
    p = requests.get(f"{BASE}/actor-runs/{run_id}", params={"token": TOKEN}, timeout=10)
    status = p.json()["data"]["status"]
    print(f"  {status}")
    if status in ("SUCCEEDED", "FAILED", "ABORTED"):
        break

if status == "SUCCEEDED":
    ds_id = p.json()["data"]["defaultDatasetId"]
    items = requests.get(
        f"{BASE}/datasets/{ds_id}/items",
        params={"token": TOKEN, "limit": 10}, timeout=10,
    ).json()
    print(f"\n{len(items)} items returned")
    for idx, item in enumerate(items):
        print(f"\n=== ITEM {idx+1} | post_type={item.get('post_type')} ===")
        print(f"  Top-level keys: {list(item.keys())}")
        # Print media/image-related fields if they exist
        for key in ("media", "image", "images", "video", "attachment", "content", "article", "document"):
            if key in item:
                print(f"  [{key}]: {json.dumps(item[key], ensure_ascii=False)[:300]}")
        # Show reshared_post keys if present
        if item.get("reshared_post"):
            rp = item["reshared_post"]
            print(f"  reshared_post keys: {list(rp.keys())}")
            for key in ("media", "image", "images", "video", "attachment", "content"):
                if key in rp:
                    print(f"  reshared_post.[{key}]: {json.dumps(rp[key], ensure_ascii=False)[:300]}")
