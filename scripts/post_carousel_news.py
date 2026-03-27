"""
Post Carousel News
──────────────────
Runs the full AI news pipeline for ONE top story and publishes it as a
3-slide carousel to Instagram.

Carousel structure:
  Slide 1 — Hook line 1  (the shocking statement)
  Slide 2 — Hook line 2  (what happened)
  Slide 3 — Hook line 3  (the consequence / why it matters)

Each slide uses the same base AI-generated image with a different text
overlay at the bottom + @username watermark at the bottom-left.

Usage:
    python scripts/post_carousel_news.py --account cognitionlabs.ai
    python scripts/post_carousel_news.py --account cognitionlabs.ai --skip-images
"""
import argparse
import logging
import os
import sys
import uuid
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
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
from services.text_overlay import TextOverlayService
from services.instagram_publisher import InstagramPublisher
from services import supabase_client as db
from supabase import create_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("post_carousel_news")

SUPABASE_BUCKET = "post-images"
AI_REDDIT_NICHE = "AI & Productivity"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _upload_image(local_path: str) -> str:
    """Upload a local PNG to Supabase Storage and return its public URL."""
    filename = f"carousel_{uuid.uuid4().hex[:8]}.png"
    storage_key = settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY
    upload_url = f"{settings.SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{filename}"
    headers = {
        "Authorization": f"Bearer {storage_key}",
        "Content-Type": "image/png",
        "x-upsert": "true",
    }
    with open(local_path, "rb") as f:
        resp = requests.post(upload_url, headers=headers, data=f, timeout=30)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Upload failed ({resp.status_code}): {resp.text[:200]}")
    return f"{settings.SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{filename}"


def _scrape_ai_sources():
    posts = []
    try:
        posts.extend(HackerNewsScraper().scrape(limit=30))
    except Exception as e:
        logger.error("HN scrape failed: %s", e)
    try:
        posts.extend(RedditScraper().scrape(niche=AI_REDDIT_NICHE, limit=30))
    except Exception as e:
        logger.error("Reddit scrape failed: %s", e)
    return posts


# ─── Main ─────────────────────────────────────────────────────────────────────

def run(account_username: str, skip_images: bool = False):
    # ── 1. Load account ───────────────────────────────────────────────────────
    accounts = db.get_active_accounts()
    account = next((a for a in accounts if a["username"] == account_username), None)
    if not account:
        logger.error("Account '%s' not found", account_username)
        sys.exit(1)
    if not account.get("access_token") or not account.get("instagram_user_id"):
        logger.error("Account '%s' missing Instagram credentials", account_username)
        sys.exit(1)

    # ── 2. Scrape + detect + score ────────────────────────────────────────────
    logger.info("Scraping AI news sources...")
    raw = _scrape_ai_sources()
    if not raw:
        logger.error("No raw posts scraped")
        sys.exit(1)

    logger.info("Detecting high-impact stories...")
    stories = NewsDetectorAgent().run(raw)
    if not stories:
        logger.error("No AI stories detected")
        sys.exit(1)

    logger.info("Scoring for virality...")
    qualified = ViralityScorerAgent().run(stories)
    if not qualified:
        logger.error("No stories passed virality threshold")
        sys.exit(1)

    story = qualified[0]
    logger.info("Top story [score=%s]: %s", story.get("total_score"), story.get("title", "")[:80])

    # ── 3. Generate hook, visual concept, image prompt ────────────────────────
    logger.info("Generating viral hook...")
    hook = ViralHookAgent().run(story)
    line1 = hook.get("line1", story.get("title", "")[:60])
    line2 = hook.get("line2", "")
    line3 = hook.get("line3", "")
    logger.info("Hook: %s | %s | %s", line1[:50], line2[:50], line3[:50])

    logger.info("Building visual concept...")
    visual = VisualStoryAgent().run(story, hook)

    logger.info("Building image prompt...")
    image_prompt = ImagePromptAgent().run(visual, story)

    # ── 4. Generate or placeholder base image ─────────────────────────────────
    if skip_images:
        image_url = "https://placehold.co/1080x1080/0a0f2c/4F46E5?text=AI+News"
        logger.info("[SKIP-IMAGES] Using placeholder image")
    else:
        logger.info("Generating image with Stability AI...")
        image_url = ImageGenerator().generate(image_prompt)
        if not image_url:
            logger.error("Image generation failed")
            sys.exit(1)

    logger.info("Base image URL: %s", image_url)

    # ── 5. Download base image ────────────────────────────────────────────────
    base_path = f"/tmp/carousel_base_{uuid.uuid4().hex[:8]}.png"
    resp = requests.get(image_url, timeout=30)
    resp.raise_for_status()
    with open(base_path, "wb") as f:
        f.write(resp.content)
    logger.info("Base image downloaded: %s", base_path)

    # ── 6. Create 3 overlaid slides ───────────────────────────────────────────
    overlay_svc = TextOverlayService()
    slide_texts = [
        line1,   # slide 1 — shocking statement
        line2,   # slide 2 — what happened
        line3,   # slide 3 — consequence
    ]
    # Drop empty lines (story may have fewer than 3 meaningful lines)
    slide_texts = [t for t in slide_texts if t.strip()]
    if not slide_texts:
        slide_texts = [story.get("title", "")[:60]]

    public_urls = []
    for i, text in enumerate(slide_texts, start=1):
        out_path = f"/tmp/carousel_slide{i}_{uuid.uuid4().hex[:6]}.png"
        overlay_svc.add_text(
            base_path, text,
            output_path=out_path,
            username=account_username,
        )
        logger.info("Slide %d overlay applied: '%s'", i, text[:60])

        public_url = _upload_image(out_path)
        public_urls.append(public_url)
        logger.info("Slide %d uploaded: %s", i, public_url)

    logger.info("%d slides ready for carousel", len(public_urls))

    # ── 7. Generate caption + hashtags ────────────────────────────────────────
    caption_body = CaptionAgent().run(story, hook)
    hashtags = HashtagAgent().run(story, hook)
    full_caption = f"{hook.get('headline_hook', line1)}\n\n{caption_body}"

    # ── 8. Publish carousel ───────────────────────────────────────────────────
    logger.info("Publishing carousel to @%s...", account_username)
    publisher = InstagramPublisher(account["access_token"])

    if len(public_urls) == 1:
        ig_post_id = publisher.publish_single_image(
            ig_user_id=account["instagram_user_id"],
            image_url=public_urls[0],
            caption=full_caption,
            hashtags=hashtags,
        )
    else:
        ig_post_id = publisher.publish_carousel(
            ig_user_id=account["instagram_user_id"],
            image_urls=public_urls,
            caption=full_caption,
            hashtags=hashtags,
        )

    logger.info("=" * 60)
    logger.info("CAROUSEL PUBLISHED SUCCESSFULLY!")
    logger.info("Instagram Post ID : %s", ig_post_id)
    logger.info("Account           : @%s", account_username)
    logger.info("Story             : %s", story.get("title", "")[:70])
    logger.info("Slides            : %d", len(public_urls))
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Post AI news carousel to Instagram")
    parser.add_argument("--account", required=True, help="Instagram account username")
    parser.add_argument("--skip-images", action="store_true",
                        help="Skip Stability AI image generation (use placeholder)")
    args = parser.parse_args()
    run(args.account, args.skip_images)
