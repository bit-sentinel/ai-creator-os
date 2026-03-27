#!/usr/bin/env python3
"""
LinkedIn scraper diagnostic & live test.
Tests both the currently-configured actor and probes alternatives.

Usage:  python scripts/test_linkedin.py
"""
import sys, os, time, json, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from config.settings import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
log = logging.getLogger("test_linkedin")

TOKEN = settings.APIFY_API_TOKEN
CURRENT_ACTOR = settings.APIFY_LINKEDIN_ACTOR
BASE = "https://api.apify.com/v2"

SEP = "─" * 60


def check_token():
    print(f"\n{SEP}\n1. TOKEN CHECK\n{SEP}")
    r = requests.get(f"{BASE}/users/me", params={"token": TOKEN}, timeout=10)
    if r.status_code == 200:
        d = r.json()["data"]
        print(f"  ✓ Valid — user={d.get('username')}  plan={d.get('plan', {}).get('id')}")
    else:
        print(f"  ✗ Invalid token: {r.status_code} — {r.text[:200]}")
        sys.exit(1)


def check_current_actor():
    print(f"\n{SEP}\n2. CURRENT ACTOR: {CURRENT_ACTOR}\n{SEP}")
    slug = CURRENT_ACTOR.replace("/", "~")

    # Metadata
    r = requests.get(f"{BASE}/acts/{slug}", params={"token": TOKEN}, timeout=10)
    if r.status_code != 200:
        print(f"  ✗ Actor not found: {r.status_code}")
        return False
    d = r.json()["data"]
    pricing = d.get("currentPricingInfo", {})
    print(f"  Name        : {d.get('name')}")
    print(f"  isPublic    : {d.get('isPublic')}")
    print(f"  pricingModel: {pricing.get('pricingModel', 'not set')}")
    print(f"  isRented    : {pricing.get('isRented', 'n/a')}")

    # Try starting a run
    r2 = requests.post(
        f"{BASE}/acts/{slug}/runs",
        json={"searchTerms": ["AI productivity"], "maxResults": 2, "sort": "RECENT"},
        params={"token": TOKEN},
        timeout=20,
    )
    if r2.status_code == 201:
        print(f"  ✓ Run started: {r2.json()['data']['id']}")
        return True
    else:
        err = r2.json().get("error", {})
        print(f"  ✗ Run failed {r2.status_code}: [{err.get('type')}] {err.get('message')}")
        return False


def try_actor(actor_id: str, payload: dict, label: str, poll_secs: int = 90) -> bool:
    """Start a run, poll it, and show a sample result."""
    print(f"\n  Testing: {actor_id}")
    slug = actor_id.replace("/", "~")

    # Check actor exists
    r = requests.get(f"{BASE}/acts/{slug}", params={"token": TOKEN}, timeout=10)
    if r.status_code != 200:
        print(f"    ✗ Not found ({r.status_code})")
        return False

    d = r.json()["data"]
    pricing = d.get("currentPricingInfo", {})
    print(f"    pricingModel={pricing.get('pricingModel', 'free')}  isRented={pricing.get('isRented', 'n/a')}")

    # Start run
    r2 = requests.post(
        f"{BASE}/acts/{slug}/runs",
        json=payload,
        params={"token": TOKEN},
        timeout=20,
    )
    if r2.status_code != 201:
        err = r2.json().get("error", {})
        print(f"    ✗ Cannot start [{err.get('type')}]: {err.get('message', r2.text[:150])}")
        return False

    run_id = r2.json()["data"]["id"]
    print(f"    ✓ Run started: {run_id}")

    # Poll
    deadline = time.time() + poll_secs
    status = "RUNNING"
    while time.time() < deadline:
        time.sleep(6)
        p = requests.get(f"{BASE}/actor-runs/{run_id}", params={"token": TOKEN}, timeout=10)
        status = p.json()["data"]["status"]
        print(f"    … {status}")
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break

    if status != "SUCCEEDED":
        print(f"    ✗ Run ended with: {status}")
        return False

    ds_id = p.json()["data"]["defaultDatasetId"]
    items = requests.get(
        f"{BASE}/datasets/{ds_id}/items",
        params={"token": TOKEN, "limit": 3},
        timeout=10,
    ).json()
    print(f"    ✓ SUCCEEDED — {len(items)} items returned")
    if items:
        print(f"    Sample keys: {list(items[0].keys())[:10]}")
        if items[0].get("text"):
            print(f"    Sample text: {items[0]['text'][:120]}...")
    return True


def probe_alternatives():
    print(f"\n{SEP}\n3. PROBING ALTERNATIVES\n{SEP}")

    alternatives = [
        # keyword-search based (closest to current use-case)
        (
            "curious_coder/linkedin-company-posts-scraper",
            {"startUrls": [{"url": "https://www.linkedin.com/company/openai/"}], "maxPosts": 3},
        ),
        (
            "apimaestro/linkedin-profile-posts",
            {"profileUrl": "https://www.linkedin.com/in/satyanadella/", "maxPosts": 3},
        ),
        # Google News as a free fallback for trend discovery
        (
            "apify/google-search-scraper",
            {"queries": ["AI productivity trends site:linkedin.com"], "maxPagesPerQuery": 1, "resultsPerPage": 5},
        ),
    ]

    viable = []
    for actor_id, payload in alternatives:
        ok = try_actor(actor_id, payload, actor_id, poll_secs=90)
        if ok:
            viable.append(actor_id)

    return viable


def main():
    print("\n══════════════════════════════════════════════════════")
    print("  LinkedIn Scraper — Diagnostic Test")
    print("══════════════════════════════════════════════════════")

    check_token()
    current_ok = check_current_actor()

    if current_ok:
        print(f"\n✅ Current actor ({CURRENT_ACTOR}) is working — no changes needed.")
        sys.exit(0)

    print(f"\n⚠️  Current actor requires rental. Probing alternatives...")
    viable = probe_alternatives()

    print(f"\n{SEP}\n4. SUMMARY\n{SEP}")
    if viable:
        print(f"\n✅ Viable replacement actors:")
        for v in viable:
            print(f"   • {v}")
        best = viable[0]
        print(f"\n   Recommended → set in .env or config/settings.py:")
        print(f"   APIFY_LINKEDIN_ACTOR={best}")
    else:
        print("\n❌ No free LinkedIn actor found on your Apify STARTER plan.")
        print("   Options:")
        print("   1. Rent 'curious_coder/linkedin-post-search-scraper' on Apify (~$10/mo)")
        print("   2. Use Reddit-only trend discovery (already working ✓)")
        print("   3. Upgrade to Apify SCALE plan which includes more actors")


if __name__ == "__main__":
    main()
