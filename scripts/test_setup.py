#!/usr/bin/env python3
"""
AI Creator OS — End-to-End Setup Tester
────────────────────────────────────────
Runs a live connectivity check against every external service
and a dry-run of each AI agent using real API keys.

Usage:
    python scripts/test_setup.py                # full test
    python scripts/test_setup.py --skip-images  # skip DALL-E (saves money)
    python scripts/test_setup.py --skip-scrape  # skip Apify actors
    python scripts/test_setup.py --unit-only    # run pytest suite only

Requires a valid .env file with real credentials.
"""
import argparse
import sys
import os
import time
import json

# ── path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── colour helpers ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

PASS  = f"{GREEN}✓ PASS{RESET}"
FAIL  = f"{RED}✗ FAIL{RESET}"
SKIP  = f"{YELLOW}⊘ SKIP{RESET}"
INFO  = f"{CYAN}ℹ{RESET}"

results = []

def section(title: str):
    print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*60}{RESET}")

def check(name: str, passed: bool, detail: str = "", skipped: bool = False):
    status = SKIP if skipped else (PASS if passed else FAIL)
    detail_str = f"  {YELLOW}{detail}{RESET}" if detail else ""
    print(f"  {status}  {name}{detail_str}")
    results.append({"name": name, "passed": passed or skipped, "skipped": skipped})

def die(msg: str):
    print(f"\n{RED}{BOLD}FATAL: {msg}{RESET}\n")
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# TEST GROUPS
# ══════════════════════════════════════════════════════════════════════════════

def test_environment():
    section("1. Environment & Config")
    try:
        from config.settings import settings
        check("Settings load from .env", True)
    except Exception as e:
        check("Settings load from .env", False, str(e))
        die("Cannot load settings — fill in .env first")

    required = [
        ("OPENAI_API_KEY",      settings.OPENAI_API_KEY),
        ("SUPABASE_URL",        settings.SUPABASE_URL),
        ("SUPABASE_KEY",        settings.SUPABASE_KEY),
        ("APIFY_API_TOKEN",     settings.APIFY_API_TOKEN),
        ("INSTAGRAM_APP_ID",    settings.INSTAGRAM_APP_ID),
        ("INSTAGRAM_APP_SECRET",settings.INSTAGRAM_APP_SECRET),
        ("API_SECRET_KEY",      settings.API_SECRET_KEY),
    ]
    for name, val in required:
        ok = bool(val) and val not in ("change-me-in-production", "sk-...", "")
        check(f"{name} is set", ok, "⚠ placeholder value" if not ok else "")

    return settings


def test_supabase(settings):
    section("2. Supabase Database")
    try:
        from services.supabase_client import get_db
        db = get_db()
        check("Supabase client initialised", True)
    except Exception as e:
        check("Supabase client initialised", False, str(e))
        return

    tables = ["accounts", "posts", "trends", "engagement_metrics",
              "strategy_memory", "content_templates", "scheduled_jobs"]
    for table in tables:
        try:
            res = db.table(table).select("*").limit(1).execute()
            check(f"Table '{table}' accessible", True,
                  f"{len(res.data)} rows (sample)")
        except Exception as e:
            check(f"Table '{table}' accessible", False, str(e))

    # Test the fuzzy dedup RPC function
    try:
        from datetime import datetime, timezone, timedelta
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        db.rpc("check_topic_similarity",
               {"p_topic": "test topic", "p_since": since, "p_threshold": 0.7}).execute()
        check("check_topic_similarity() RPC function", True)
    except Exception as e:
        check("check_topic_similarity() RPC function", False,
              "Run database/schema.sql in Supabase first")

    # Check for active accounts
    try:
        from services import supabase_client as dbc
        accounts = dbc.get_active_accounts()
        check(f"Active accounts in DB", len(accounts) > 0,
              f"Found {len(accounts)} — run scripts/setup_accounts.py if 0")
    except Exception as e:
        check("Active accounts in DB", False, str(e))


def test_openai(settings):
    section("3. OpenAI API (GPT-4o + DALL-E)")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=5,
        )
        reply = resp.choices[0].message.content.strip()
        check("GPT-4o chat completion", "OK" in reply.upper(), f'response: "{reply}"')
    except Exception as e:
        check("GPT-4o chat completion", False, str(e))


def test_dalle(settings, skip: bool):
    if skip:
        check("DALL-E 3 image generation", True, skipped=True)
        return

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.images.generate(
            model=settings.DALLE_MODEL,
            prompt="A simple blue circle on a white background",
            size="1024x1024",
            quality="standard",
            n=1,
        )
        url = resp.data[0].url
        check("DALL-E 3 image generation", bool(url), f"URL: {url[:60]}…")
    except Exception as e:
        check("DALL-E 3 image generation", False, str(e))


def test_apify(settings, skip: bool):
    section("4. Apify Scrapers")
    if skip:
        check("LinkedIn scraper actor", True, skipped=True)
        check("Reddit scraper actor",   True, skipped=True)
        return

    import requests
    APIFY_BASE = "https://api.apify.com/v2"
    token = settings.APIFY_API_TOKEN

    # Just verify the token is valid — don't run a full actor (costs money)
    try:
        resp = requests.get(f"{APIFY_BASE}/users/me",
                            params={"token": token}, timeout=10)
        resp.raise_for_status()
        username = resp.json().get("data", {}).get("username", "unknown")
        check("Apify API token valid", True, f"account: {username}")
    except Exception as e:
        check("Apify API token valid", False, str(e))
        return

    # Verify the actor IDs exist
    for actor_id, label in [
        (settings.APIFY_LINKEDIN_ACTOR, "LinkedIn actor"),
        (settings.APIFY_REDDIT_ACTOR,   "Reddit actor"),
    ]:
        try:
            actor_slug = actor_id.replace("/", "~")
            resp = requests.get(f"{APIFY_BASE}/acts/{actor_slug}",
                                params={"token": token}, timeout=10)
            ok = resp.status_code == 200
            name = resp.json().get("data", {}).get("name", actor_id) if ok else ""
            check(f"{label} exists", ok, name)
        except Exception as e:
            check(f"{label} exists", False, str(e))


def test_agents(settings, skip_images: bool):
    section("5. AI Agents (dry run)")

    TOPIC = "5 AI tools that save 10 hours a week"
    NICHE = "AI & Productivity"
    HOOK  = "5 AI tools saving me 10h every week"

    # HookAgent
    try:
        from agents.hook_agent import HookAgent
        agent = HookAgent()
        result = agent.run(topic=TOPIC, niche=NICHE)
        ok = bool(result.get("hook"))
        check("HookAgent — generates hook", ok, f'"{result.get("hook", "")[:60]}"')
    except Exception as e:
        check("HookAgent — generates hook", False, str(e))

    # ContentAgent
    content_result = None
    try:
        from agents.content_agent import ContentAgent
        agent = ContentAgent()
        content_result = agent.run(topic=TOPIC, hook=HOOK, niche=NICHE)
        slide_count = len(content_result.get("slides", []))
        check("ContentAgent — generates slides", slide_count == 5,
              f"{slide_count} slides")
    except Exception as e:
        check("ContentAgent — generates slides", False, str(e))

    # CarouselAgent
    carousel_result = None
    if content_result:
        try:
            from agents.carousel_agent import CarouselAgent
            agent = CarouselAgent()
            carousel_result = agent.run(
                content=content_result, topic=TOPIC,
                hook=HOOK, niche=NICHE,
            )
            ok = (
                len(carousel_result.get("slides", [])) == 5 and
                bool(carousel_result.get("caption")) and
                len(carousel_result.get("hashtags", [])) > 0
            )
            check("CarouselAgent — caption + hashtags", ok,
                  f'{len(carousel_result.get("hashtags", []))} hashtags')
        except Exception as e:
            check("CarouselAgent — caption + hashtags", False, str(e))

    # DesignAgent
    if carousel_result and not skip_images:
        try:
            from agents.design_agent import DesignAgent
            agent = DesignAgent()
            slides = carousel_result["slides"][:1]   # only 1 slide to save cost
            updated = agent.run(slides=slides, niche=NICHE)
            ok = bool(updated[0].get("image_url"))
            check("DesignAgent — DALL-E image (1 slide)", ok,
                  updated[0].get("image_url", "")[:60])
        except Exception as e:
            check("DesignAgent — DALL-E image", False, str(e))
    elif skip_images:
        check("DesignAgent — DALL-E image", True, skipped=True)


def test_api_server():
    section("6. FastAPI Server")
    import requests

    base = "http://localhost:8000"
    try:
        resp = requests.get(f"{base}/health", timeout=5)
        resp.raise_for_status()
        check("Health endpoint responds", True,
              f"status={resp.json().get('status')}")
    except requests.ConnectionError:
        check("Health endpoint responds", False,
              "Server not running — start with: python main.py --serve")
        return
    except Exception as e:
        check("Health endpoint responds", False, str(e))
        return

    # Auth check
    try:
        from config.settings import settings
        resp = requests.get(f"{base}/accounts",
                            headers={"x-api-key": settings.API_SECRET_KEY},
                            timeout=5)
        check("API key auth works", resp.status_code == 200,
              f"HTTP {resp.status_code}")
    except Exception as e:
        check("API key auth works", False, str(e))

    try:
        resp = requests.get(f"{base}/accounts",
                            headers={"x-api-key": "wrong-key"}, timeout=5)
        check("Invalid key returns 401", resp.status_code == 401,
              f"HTTP {resp.status_code}")
    except Exception as e:
        check("Invalid key returns 401", False, str(e))


def test_unit_suite():
    section("7. Unit Test Suite (pytest)")
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short",
         "--no-header", "-q"],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    output_lines = (result.stdout + result.stderr).strip().splitlines()
    for line in output_lines[-20:]:   # show last 20 lines
        print(f"    {line}")

    passed = result.returncode == 0
    # Extract summary line
    summary = next((l for l in reversed(output_lines) if "passed" in l or "failed" in l), "")
    check("All unit tests pass", passed, summary)


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

def print_summary():
    section("Summary")
    total   = len(results)
    passed  = sum(1 for r in results if r["passed"] and not r["skipped"])
    skipped = sum(1 for r in results if r["skipped"])
    failed  = sum(1 for r in results if not r["passed"])

    print(f"\n  Total:   {total}")
    print(f"  {GREEN}Passed:  {passed}{RESET}")
    print(f"  {YELLOW}Skipped: {skipped}{RESET}")
    print(f"  {RED}Failed:  {failed}{RESET}")

    if failed:
        print(f"\n  {RED}Failed checks:{RESET}")
        for r in results:
            if not r["passed"]:
                print(f"    • {r['name']}")
        print(f"\n  {YELLOW}Fix the failures above before running live pipelines.{RESET}\n")
        return False
    else:
        print(f"\n  {GREEN}{BOLD}All checks passed — system is ready!{RESET}\n")
        return True


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Creator OS setup tester")
    parser.add_argument("--skip-images", action="store_true",
                        help="Skip DALL-E image generation test (saves API cost)")
    parser.add_argument("--skip-scrape", action="store_true",
                        help="Skip Apify actor validation")
    parser.add_argument("--unit-only",   action="store_true",
                        help="Only run the pytest unit test suite")
    args = parser.parse_args()

    print(f"\n{BOLD}AI Creator OS — Setup Test Runner{RESET}")
    print(f"{'='*60}")

    if args.unit_only:
        test_unit_suite()
    else:
        settings = test_environment()
        test_supabase(settings)
        test_openai(settings)
        test_dalle(settings, skip=args.skip_images)
        test_apify(settings, skip=args.skip_scrape)
        test_agents(settings, skip_images=args.skip_images)
        test_api_server()
        test_unit_suite()

    ok = print_summary()
    sys.exit(0 if ok else 1)
