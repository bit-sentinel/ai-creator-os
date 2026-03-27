"""
AI News Storytelling Pipeline
──────────────────────────────
A breaking-news engine for Instagram. Transforms viral AI developments
into cinematic single-image posts with dramatic hooks.

Pipeline stages:
  1. Scrape  — HackerNews + Reddit AI communities
  2. Detect  — NewsDetectorAgent filters for high-impact AI stories
  3. Score   — ViralityScorerAgent ranks by shock/curiosity/visual/relevance
  4. Create  — Per qualified story:
               a. ViralHookAgent     → 3-line dramatic hook
               b. VisualStoryAgent   → cinematic scene concept
               c. ImagePromptAgent   → Stability AI prompt
               d. ImageGenerator     → generate the image
               e. CaptionAgent       → 1-2 line punchy caption
               f. HashtagAgent       → 8-10 hashtags
               g. Save scheduled post to DB

Usage:
  python main.py --pipeline ai_news
  python main.py --pipeline ai_news --account FutureOfWork
"""
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from agents.news_detector_agent import NewsDetectorAgent
from agents.virality_scorer_agent import ViralityScorerAgent
from agents.viral_hook_agent import ViralHookAgent
from agents.visual_story_agent import VisualStoryAgent
from agents.image_prompt_agent import ImagePromptAgent
from agents.caption_agent import CaptionAgent
from agents.hashtag_agent import HashtagAgent
from services.hackernews_scraper import HackerNewsScraper
from services.reddit_scraper import RedditScraper
from services.image_generator import ImageGenerator
from services import supabase_client as db

logger = logging.getLogger("ai_news_pipeline")

# Reddit communities focused on AI news
AI_REDDIT_NICHE = "AI & Productivity"   # maps to r/artificial, r/MachineLearning, r/ChatGPT, etc.


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

def run_ai_news_pipeline(
    username: Optional[str] = None,
    max_posts_per_account: int = 3,
    skip_images: bool = False,
) -> None:
    """
    Discover, score, and schedule high-impact AI news posts.

    Args:
        username:              Limit to a single account username, or None for all.
        max_posts_per_account: Max posts to generate per account per run.
        skip_images:           If True, skip Stability AI calls and use a placeholder
                               image URL. Useful for E2E testing without spending credits.
    """
    logger.info("=== PIPELINE: AI News Storytelling Engine ===")

    accounts = _get_accounts(username)
    if not accounts:
        logger.warning("No active accounts found (filter: %s)", username or "none")
        return

    # ── Stage 1: Scrape ───────────────────────────────────────────────────────
    logger.info("Stage 1 — Scraping AI news sources (HN + Reddit)...")
    raw_posts = _scrape_ai_sources()
    logger.info("Collected %d raw posts total", len(raw_posts))

    if not raw_posts:
        logger.warning("No raw posts collected — pipeline aborted")
        return

    # ── Stage 2: Detect AI news stories ──────────────────────────────────────
    logger.info("Stage 2 — Filtering for high-impact AI stories...")
    detector = NewsDetectorAgent()
    stories = detector.run(raw_posts)
    logger.info("Detected %d qualifying AI news stories", len(stories))

    if not stories:
        logger.warning("No AI news stories detected — pipeline aborted")
        return

    # ── Stage 3: Virality scoring ─────────────────────────────────────────────
    logger.info("Stage 3 — Scoring stories for virality...")
    scorer = ViralityScorerAgent()
    qualified = scorer.run(stories)
    logger.info("%d stories passed virality threshold", len(qualified))

    if not qualified:
        logger.warning("No stories met virality threshold — pipeline aborted")
        return

    # ── Stage 4: Generate content per account ────────────────────────────────
    hook_agent = ViralHookAgent()
    visual_agent = VisualStoryAgent()
    prompt_agent = ImagePromptAgent()
    caption_agent = CaptionAgent()
    hashtag_agent = HashtagAgent()
    image_generator = ImageGenerator()

    for account in accounts:
        logger.info("Generating posts for account: @%s", account["username"])
        top_stories = qualified[:max_posts_per_account]
        generated = 0

        for story in top_stories:
            try:
                ok = _generate_and_schedule_post(
                    account=account,
                    story=story,
                    hook_agent=hook_agent,
                    visual_agent=visual_agent,
                    prompt_agent=prompt_agent,
                    caption_agent=caption_agent,
                    hashtag_agent=hashtag_agent,
                    image_generator=image_generator,
                    skip_images=skip_images,
                )
                if ok:
                    generated += 1
            except Exception as e:
                logger.error(
                    "Post generation failed for story '%s': %s",
                    story.get("title", "")[:60], e,
                )

        logger.info(
            "Account @%s — %d/%d posts scheduled",
            account["username"], generated, len(top_stories),
        )

    logger.info("=== AI News Pipeline Complete ===")


# ═════════════════════════════════════════════════════════════════════════════
# CORE GENERATION LOGIC
# ═════════════════════════════════════════════════════════════════════════════

def _generate_and_schedule_post(
    account: Dict,
    story: Dict,
    hook_agent: ViralHookAgent,
    visual_agent: VisualStoryAgent,
    prompt_agent: ImagePromptAgent,
    caption_agent: CaptionAgent,
    hashtag_agent: HashtagAgent,
    image_generator: ImageGenerator,
    skip_images: bool = False,
) -> bool:
    """
    Run the full content chain for one story.
    Returns True if the post was successfully scheduled.
    """
    title = story.get("title", "untitled")
    logger.info(
        "Processing: [score=%s] %s",
        story.get("total_score", "?"), title[:70],
    )

    # a. 3-line viral hook
    hook = hook_agent.run(story)

    # b. Cinematic visual scene concept
    visual = visual_agent.run(story, hook)

    # c. Stability AI image prompt
    image_prompt = prompt_agent.run(visual, story)

    # d. Generate image (skip in test mode to avoid spending credits)
    if skip_images:
        image_url = "https://placehold.co/1080x1080/0a0f2c/4F46E5?text=AI+News+Test"
        logger.info("[SKIP-IMAGES] Using placeholder for: %s", title[:60])
    else:
        image_url = image_generator.generate(image_prompt)
        if not image_url:
            logger.warning("Image generation failed for: %s", title[:60])
            image_url = ""

    # e. Short punchy caption
    caption_body = caption_agent.run(story, hook)

    # f. Hashtags
    hashtags = hashtag_agent.run(story, hook)

    # g. Assemble full caption: hook + body
    full_caption = f"{hook['headline_hook']}\n\n{caption_body}"

    # h. Dedup check
    content_hash = _make_hash(title + hook.get("line1", ""))
    if db.post_hash_exists(content_hash):
        logger.info("Duplicate post skipped: %s", title[:60])
        return False

    # i. Schedule
    scheduled_time = _compute_next_slot(account)
    post_record = {
        "account_id": account["account_id"],
        "topic": title,
        "hook": hook.get("headline_hook", ""),
        "slides": [
            {
                "slide_number": 1,
                "role": "news_story",
                "title": hook.get("line1", ""),
                "content": hook.get("headline_hook", ""),
                "image_url": image_url,
                "image_prompt_final": image_prompt,
                "visual_scene": visual.get("visual_scene", ""),
                # Metadata stored in slide JSON (no extra DB columns needed)
                "pipeline": "ai_news",
                "story_type": story.get("story_type", ""),
                "virality_score": story.get("total_score", 0),
                "source_url": story.get("source_url", ""),
            }
        ],
        "caption": full_caption,
        "hashtags": hashtags,
        "image_urls": [image_url] if image_url else [],
        "status": "scheduled",
        "scheduled_at": scheduled_time.isoformat(),
        "content_hash": content_hash,
    }

    db.create_post(post_record)
    logger.info(
        "Scheduled for @%s at %s | score=%s | story: %s",
        account["username"],
        scheduled_time.strftime("%Y-%m-%d %H:%M UTC"),
        story.get("total_score", 0),
        title[:60],
    )
    return True


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _scrape_ai_sources() -> List[Dict]:
    """Scrape HackerNews and Reddit AI communities."""
    all_posts: List[Dict] = []

    # Hacker News (free public API, no auth)
    try:
        hn_posts = HackerNewsScraper().scrape(limit=30)
        logger.info("HN: %d posts", len(hn_posts))
        all_posts.extend(hn_posts)
    except Exception as e:
        logger.error("HackerNews scrape failed: %s", e)

    # Reddit AI communities via existing RedditScraper + Apify
    try:
        reddit_posts = RedditScraper().scrape(niche=AI_REDDIT_NICHE, limit=30)
        logger.info("Reddit AI: %d posts", len(reddit_posts))
        all_posts.extend(reddit_posts)
    except Exception as e:
        logger.error("Reddit scrape failed: %s", e)

    return all_posts


def _get_accounts(username: Optional[str] = None) -> List[Dict]:
    accounts = db.get_active_accounts()
    if username:
        accounts = [a for a in accounts if a["username"] == username]
    return accounts


def _compute_next_slot(account: Dict) -> datetime:
    preferred_times = account.get("preferred_post_times") or [
        "07:00", "12:00", "17:00", "20:00"
    ]
    now = datetime.now(timezone.utc)
    today = now.date()

    for time_str in preferred_times:
        hour, minute = map(int, time_str.split(":"))
        candidate = datetime(
            today.year, today.month, today.day, hour, minute, tzinfo=timezone.utc
        )
        if candidate > now:
            return candidate

    # All today's slots passed — use first slot tomorrow
    hour, minute = map(int, preferred_times[0].split(":"))
    tomorrow = today + timedelta(days=1)
    return datetime(
        tomorrow.year, tomorrow.month, tomorrow.day, hour, minute, tzinfo=timezone.utc
    )


def _make_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
