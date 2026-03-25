"""
AI Creator OS — Main Orchestrator
───────────────────────────────────
Runs the five automation pipelines:
  1. trend_discovery     — Scan LinkedIn/Reddit for viral topics
  2. content_creation    — Generate carousel content
  3. publishing          — Publish scheduled posts
  4. analytics           — Collect engagement metrics
  5. learning            — Update strategy memory

Usage:
  python main.py --pipeline trend_discovery
  python main.py --pipeline content_creation --account ai_growth_hacks
  python main.py --pipeline all          # Run all in sequence
  python main.py --serve                 # Start FastAPI server (for n8n)
"""
import argparse
import logging
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

import yaml

from config.settings import settings
from agents.trend_agent import TrendAgent
from agents.hook_agent import HookAgent
from agents.content_agent import ContentAgent
from agents.carousel_agent import CarouselAgent
from agents.design_agent import DesignAgent
from agents.analytics_agent import AnalyticsAgent
from agents.learning_agent import LearningAgent
from services.instagram_publisher import InstagramPublisher
from services import supabase_client as db

# ─── Logging setup ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("creator_os.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")

# Load account config
with open("config/accounts.yaml") as f:
    ACCOUNT_CONFIG_YAML = yaml.safe_load(f)


# ═════════════════════════════════════════════════════════════════════════════
# PIPELINE 1 — TREND DISCOVERY
# ═════════════════════════════════════════════════════════════════════════════

def run_trend_discovery(username: Optional[str] = None) -> None:
    """Scan LinkedIn and Reddit for viral trends for each active account."""
    logger.info("=== PIPELINE: Trend Discovery ===")
    agent = TrendAgent()
    accounts = _get_accounts(username)

    for account in accounts:
        try:
            trends = agent.run(
                niche=account["niche"],
                account_id=account["account_id"],
            )
            logger.info(
                "Account '%s': discovered %d new trends",
                account["username"], len(trends),
            )
            _log_job(account["account_id"], "trend_discovery", {"trends_found": len(trends)})
        except Exception as e:
            logger.error("Trend discovery failed for %s: %s", account["username"], e)


# ═════════════════════════════════════════════════════════════════════════════
# PIPELINE 2 — CONTENT CREATION
# ═════════════════════════════════════════════════════════════════════════════

def run_content_creation(username: Optional[str] = None) -> None:
    """Generate carousel content for each account using unused trends."""
    logger.info("=== PIPELINE: Content Creation ===")

    hook_agent = HookAgent()
    content_agent = ContentAgent()
    carousel_agent = CarouselAgent()
    design_agent = DesignAgent()

    accounts = _get_accounts(username)
    account_configs = {a["username"]: a for a in ACCOUNT_CONFIG_YAML.get("accounts", [])}

    for account in accounts:
        try:
            memory = db.get_strategy_memory(account["account_id"])
            templates = db.get_templates(niche=account["niche"])
            template = templates[0] if templates else None
            account_yaml = account_configs.get(account["username"], {})

            # How many posts to generate today?
            posts_needed = account.get("posting_frequency", settings.MAX_POSTS_PER_PAGE_PER_DAY)
            trends = db.get_unused_trends(account["niche"], limit=posts_needed)

            if not trends:
                logger.warning("No unused trends for account '%s'", account["username"])
                continue

            logger.info(
                "Account '%s': generating %d posts from %d trends",
                account["username"], len(trends), len(trends),
            )

            for trend in trends:
                try:
                    _create_single_post(
                        account=account,
                        trend=trend,
                        hook_agent=hook_agent,
                        content_agent=content_agent,
                        carousel_agent=carousel_agent,
                        design_agent=design_agent,
                        memory=memory,
                        template=template,
                        account_yaml=account_yaml,
                    )
                    db.mark_trend_used(trend["trend_id"])
                except Exception as inner_e:
                    logger.error(
                        "Failed to create post for trend '%s': %s",
                        trend.get("topic", "")[:60], inner_e,
                    )
        except Exception as e:
            logger.error("Content creation failed for %s: %s", account["username"], e)


def _create_single_post(
    account, trend, hook_agent, content_agent, carousel_agent,
    design_agent, memory, template, account_yaml,
) -> None:
    topic = trend["topic"]

    # 1. Generate hook
    hook_result = hook_agent.run(topic=topic, niche=account["niche"], strategy_memory=memory)
    hook = hook_result["hook"]

    # 2. Generate content
    content = content_agent.run(
        topic=topic, hook=hook, niche=account["niche"],
        strategy_memory=memory, template=template,
    )

    # 3. Build carousel payload (slides + caption + hashtags + hash)
    carousel = carousel_agent.run(
        content=content, topic=topic, hook=hook,
        niche=account["niche"], account_config=account_yaml,
        strategy_memory=memory,
    )

    # Duplicate check
    if db.post_hash_exists(carousel["content_hash"]):
        logger.info("Duplicate post skipped for topic: %s", topic[:60])
        return

    # 4. Generate images
    slides_with_images = design_agent.run(
        slides=carousel["slides"],
        niche=account["niche"],
        account_username=account["username"],
    )

    # 5. Schedule post
    scheduled_time = _compute_next_slot(account)
    post_record = {
        "account_id": account["account_id"],
        "topic": topic,
        "hook": hook,
        "slides": slides_with_images,
        "caption": carousel["caption"],
        "hashtags": carousel["hashtags"],
        "image_urls": [s.get("image_url", "") for s in slides_with_images],
        "status": "scheduled",
        "scheduled_at": scheduled_time.isoformat(),
        "content_hash": carousel["content_hash"],
    }

    saved = db.create_post(post_record)
    logger.info(
        "Post created and scheduled for %s at %s | topic: %s",
        account["username"], scheduled_time.strftime("%Y-%m-%d %H:%M UTC"), topic[:60],
    )


# ═════════════════════════════════════════════════════════════════════════════
# PIPELINE 3 — PUBLISHING
# ═════════════════════════════════════════════════════════════════════════════

def run_publishing(username: Optional[str] = None) -> None:
    """Publish all posts scheduled for right now (within the next 15 minutes)."""
    logger.info("=== PIPELINE: Publishing ===")
    accounts = _get_accounts(username)
    now = datetime.now(timezone.utc)
    window = now + timedelta(minutes=15)

    for account in accounts:
        if not account.get("access_token") or not account.get("instagram_user_id"):
            logger.warning("Account '%s' missing credentials — skipping", account["username"])
            continue

        publisher = InstagramPublisher(account["access_token"])
        posts = db.get_scheduled_posts(account["account_id"], before=window)

        for post in posts:
            try:
                image_urls = [s.get("image_url", "") for s in post.get("slides", []) if s.get("image_url")]
                if not image_urls:
                    logger.warning("Post %s has no images — skipping", post["post_id"])
                    continue

                db.update_post(post["post_id"], {"status": "publishing"})

                post_id = publisher.publish_carousel(
                    ig_user_id=account["instagram_user_id"],
                    image_urls=image_urls,
                    caption=post["caption"],
                    hashtags=post.get("hashtags", []),
                )

                db.update_post(post["post_id"], {
                    "status": "published",
                    "instagram_post_id": post_id,
                    "posted_at": datetime.now(timezone.utc).isoformat(),
                })
                logger.info(
                    "Published post %s for '%s': IG post ID %s",
                    post["post_id"][:8], account["username"], post_id,
                )
            except Exception as e:
                logger.error("Failed to publish post %s: %s", post["post_id"][:8], e)
                db.update_post(post["post_id"], {"status": "failed", "error_log": str(e)})


# ═════════════════════════════════════════════════════════════════════════════
# PIPELINE 4 — ANALYTICS
# ═════════════════════════════════════════════════════════════════════════════

def run_analytics(username: Optional[str] = None) -> None:
    """Collect engagement metrics for all published posts."""
    logger.info("=== PIPELINE: Analytics ===")
    agent = AnalyticsAgent()
    for account in _get_accounts(username):
        try:
            metrics = agent.run(account)
            logger.info(
                "Analytics collected for '%s': %d posts updated",
                account["username"], len(metrics),
            )
        except Exception as e:
            logger.error("Analytics failed for %s: %s", account["username"], e)


# ═════════════════════════════════════════════════════════════════════════════
# PIPELINE 5 — LEARNING
# ═════════════════════════════════════════════════════════════════════════════

def run_learning(username: Optional[str] = None) -> None:
    """Analyse engagement data and update strategy memory for each account."""
    logger.info("=== PIPELINE: Learning & Optimization ===")
    agent = LearningAgent()
    for account in _get_accounts(username):
        try:
            memory = agent.run(account)
            if memory:
                logger.info(
                    "Strategy updated for '%s': %d best topics, %d best hooks",
                    account["username"],
                    len(memory.get("best_topics", [])),
                    len(memory.get("best_hooks", [])),
                )
        except Exception as e:
            logger.error("Learning failed for %s: %s", account["username"], e)


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _get_accounts(username: Optional[str] = None):
    accounts = db.get_active_accounts()
    if username:
        accounts = [a for a in accounts if a["username"] == username]
    if not accounts:
        logger.warning("No active accounts found (filter: %s)", username or "none")
    return accounts


def _compute_next_slot(account: Dict) -> datetime:
    """
    Find the next available posting slot for an account.
    Uses preferred_post_times from the account config.
    """
    preferred_times = account.get("preferred_post_times") or ["07:00", "12:00", "17:00", "20:00"]
    now = datetime.now(timezone.utc)
    today = now.date()

    for time_str in preferred_times:
        hour, minute = map(int, time_str.split(":"))
        candidate = datetime(today.year, today.month, today.day, hour, minute, tzinfo=timezone.utc)
        if candidate > now:
            return candidate

    # All today's slots passed — schedule for first slot tomorrow
    hour, minute = map(int, preferred_times[0].split(":"))
    tomorrow = today + timedelta(days=1)
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, minute, tzinfo=timezone.utc)


def _log_job(account_id: str, job_type: str, result: dict) -> None:
    try:
        db.log_job({
            "account_id": account_id,
            "job_type": job_type,
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
            "result": result,
        })
    except Exception:
        pass  # Non-critical — don't let job logging break pipelines


# ═════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="AI Creator OS")
    parser.add_argument(
        "--pipeline",
        choices=["trend_discovery", "content_creation", "publishing", "analytics", "learning", "all"],
        help="Which pipeline to run",
    )
    parser.add_argument("--account", type=str, help="Limit to a specific account username")
    parser.add_argument("--serve", action="store_true", help="Start the FastAPI server")
    args = parser.parse_args()

    if args.serve:
        import uvicorn
        from api.routes import app
        logger.info("Starting API server on %s:%d", settings.API_HOST, settings.API_PORT)
        uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
        return

    pipeline_map = {
        "trend_discovery": run_trend_discovery,
        "content_creation": run_content_creation,
        "publishing": run_publishing,
        "analytics": run_analytics,
        "learning": run_learning,
    }

    if args.pipeline == "all":
        for name, fn in pipeline_map.items():
            logger.info("Running pipeline: %s", name)
            fn(username=args.account)
    elif args.pipeline:
        pipeline_map[args.pipeline](username=args.account)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
