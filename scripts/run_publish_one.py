"""
End-to-End Single Post Publisher
─────────────────────────────────
Runs the full pipeline for @1min_ai_lessons and immediately publishes
ONE post to Instagram:

  1. Trend Discovery  — scrape Reddit for fresh AI & Productivity trends
  2. Content Creation — hook → content → carousel (AI agents)
  3. Slide Images     — generate branded 1080x1080 slides with Pillow
  4. Image Hosting    — upload slides to catbox.moe (free, public, no auth)
  5. Publish          — post carousel to Instagram via Graph API

Usage:
  python scripts/run_publish_one.py
"""

import io
import json
import logging
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()

from config.settings import settings
from agents.trend_agent import TrendAgent
from agents.hook_agent import HookAgent
from agents.content_agent import ContentAgent
from agents.carousel_agent import CarouselAgent
from services.instagram_publisher import InstagramPublisher
from services import supabase_client as db

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("e2e_publish")

# ─── Constants ───────────────────────────────────────────────────────────────
USERNAME   = "1min_ai_lessons"
IG_USER_ID = "26478207988482384"
NICHE      = "AI & Productivity"

# Slide design
SLIDE_SIZE     = (1080, 1080)
BG_COLOR       = (15, 15, 35)          # deep navy
ACCENT_COLOR   = (99, 102, 241)        # indigo
TEXT_COLOR     = (255, 255, 255)       # white
SUBTEXT_COLOR  = (180, 180, 200)       # light grey
HANDLE         = "@1min_ai_lessons"

# Font search path (macOS system fonts)
FONT_PATHS = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Arial.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/SFNS.ttf",
    "/System/Library/Fonts/SFNSDisplay.ttf",
]

OUT_DIR = Path(__file__).resolve().parent.parent / "test" / "e2e_publish"


# ═════════════════════════════════════════════════════════════════════════════
# STEP 1 — TREND DISCOVERY
# ═════════════════════════════════════════════════════════════════════════════

def discover_trend(account: Dict) -> Optional[Dict]:
    """Return one unused trend, running discovery if needed."""
    # Check for existing unused trends first
    existing = db.get_unused_trends(NICHE, limit=1)
    if existing:
        log.info("Using existing trend: %s", existing[0]["topic"][:80])
        return existing[0]

    # Run trend discovery
    log.info("No unused trends found — running trend discovery...")
    agent = TrendAgent()
    trends = agent.run(niche=NICHE, account_id=account["account_id"])
    log.info("Discovered %d new trends", len(trends))

    fresh = db.get_unused_trends(NICHE, limit=1)
    if not fresh:
        log.error("Still no unused trends after discovery.")
        return None
    log.info("Using trend: %s", fresh[0]["topic"][:80])
    return fresh[0]


# ═════════════════════════════════════════════════════════════════════════════
# STEP 2 — CONTENT CREATION (AI agents)
# ═════════════════════════════════════════════════════════════════════════════

def create_content(account: Dict, trend: Dict) -> Optional[Dict]:
    """Run hook → content → carousel agents and return carousel dict."""
    topic = trend["topic"]
    memory = db.get_strategy_memory(account["account_id"])

    log.info("Generating hook for: %s", topic[:60])
    hook_result = HookAgent().run(topic=topic, niche=NICHE, strategy_memory=memory)
    hook = hook_result["hook"]
    log.info("Hook: %s", hook[:80])

    log.info("Generating content slides...")
    content = ContentAgent().run(
        topic=topic, hook=hook, niche=NICHE,
        strategy_memory=memory, template=None,
    )

    log.info("Building carousel structure...")
    # Load account yaml config for hashtags/tone
    import yaml
    with open("config/accounts.yaml") as f:
        yaml_cfg = yaml.safe_load(f)
    account_yaml = next(
        (a for a in yaml_cfg.get("accounts", []) if a["username"] == USERNAME), {}
    )

    carousel = CarouselAgent().run(
        content=content, topic=topic, hook=hook,
        niche=NICHE, account_config=account_yaml,
        strategy_memory=memory,
    )

    log.info("Generated %d slides, caption length=%d chars",
             len(carousel.get("slides", [])), len(carousel.get("caption", "")))
    return carousel


# ═════════════════════════════════════════════════════════════════════════════
# STEP 3 — GENERATE SLIDE IMAGES (Pillow)
# ═════════════════════════════════════════════════════════════════════════════

def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a system font or fall back to Pillow default."""
    for path in FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    color: Tuple[int, int, int],
    x: int,
    y: int,
    max_width: int,
    line_spacing: int = 10,
) -> int:
    """Draw word-wrapped text, returns the y position after the last line."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    for line in lines:
        draw.text((x, y), line, font=font, fill=color)
        bbox = draw.textbbox((x, y), line, font=font)
        y += (bbox[3] - bbox[1]) + line_spacing

    return y


def generate_slide(
    text: str,
    slide_num: int,
    total_slides: int,
    is_cover: bool = False,
) -> Image.Image:
    """Generate a single 1080x1080 branded slide image."""
    img = Image.new("RGB", SLIDE_SIZE, BG_COLOR)
    draw = ImageDraw.Draw(img)

    # ── Accent bar (left edge) ──────────────────────────────────────────────
    draw.rectangle([0, 0, 8, 1080], fill=ACCENT_COLOR)

    # ── Top badge ──────────────────────────────────────────────────────────
    badge_font = _load_font(28)
    badge_text = "AI LESSON"
    draw.text((40, 40), badge_text, font=badge_font, fill=ACCENT_COLOR)

    # ── Main text ──────────────────────────────────────────────────────────
    if is_cover:
        font = _load_font(72)
        y_start = 200
    else:
        font = _load_font(56)
        y_start = 180

    text_margin = 40
    max_text_width = SLIDE_SIZE[0] - text_margin * 2 - 20

    _draw_wrapped_text(
        draw, text, font, TEXT_COLOR,
        x=text_margin + 20, y=y_start,
        max_width=max_text_width,
        line_spacing=18,
    )

    # ── Handle (bottom left) ───────────────────────────────────────────────
    handle_font = _load_font(32)
    draw.text((40, 1020), HANDLE, font=handle_font, fill=ACCENT_COLOR)

    # ── Slide counter (bottom right) ───────────────────────────────────────
    counter_text = f"{slide_num}/{total_slides}"
    counter_font = _load_font(32)
    bbox = draw.textbbox((0, 0), counter_text, font=counter_font)
    cw = bbox[2] - bbox[0]
    draw.text((SLIDE_SIZE[0] - cw - 40, 1020), counter_text,
               font=counter_font, fill=SUBTEXT_COLOR)

    # ── Divider line ───────────────────────────────────────────────────────
    draw.rectangle([40, 1008, 1040, 1010], fill=(50, 50, 70))

    return img


def generate_all_slides(slides: List[Dict]) -> List[Path]:
    """Generate all slide images, return list of local file paths."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    total = len(slides)

    for i, slide in enumerate(slides):
        text = slide.get("text") or slide.get("content") or slide.get("hook") or str(slide)
        # Truncate to avoid overflow
        if len(text) > 220:
            text = text[:217] + "..."

        img = generate_slide(
            text=text,
            slide_num=i + 1,
            total_slides=total,
            is_cover=(i == 0),
        )
        path = OUT_DIR / f"slide_{i+1:02d}.jpg"
        img.save(path, "JPEG", quality=92)
        log.info("  Slide %d/%d saved: %s", i + 1, total, path.name)
        paths.append(path)

    return paths


# ═════════════════════════════════════════════════════════════════════════════
# STEP 4 — UPLOAD IMAGES (catbox.moe — free, no auth, HTTPS)
# ═════════════════════════════════════════════════════════════════════════════

def upload_image(path: Path) -> Optional[str]:
    """Upload one image to catbox.moe, return the public HTTPS URL."""
    try:
        with open(path, "rb") as f:
            resp = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": (path.name, f, "image/jpeg")},
                timeout=60,
            )
        resp.raise_for_status()
        url = resp.text.strip()
        if url.startswith("https://"):
            log.info("  Uploaded: %s → %s", path.name, url)
            return url
        log.error("  catbox returned unexpected: %s", url[:100])
        return None
    except Exception as e:
        log.error("  Upload failed for %s: %s", path.name, e)
        return None


def upload_all_slides(paths: List[Path]) -> List[str]:
    """Upload slides and return list of public URLs."""
    log.info("Uploading %d slides to catbox.moe...", len(paths))
    urls = []
    for path in paths:
        url = upload_image(path)
        if url:
            urls.append(url)
        else:
            log.error("Failed to upload %s — aborting", path.name)
            return []
    return urls


# ═════════════════════════════════════════════════════════════════════════════
# STEP 5 — PUBLISH TO INSTAGRAM
# ═════════════════════════════════════════════════════════════════════════════

def publish(image_urls: List[str], caption: str, hashtags: List[str]) -> Optional[str]:
    """Publish carousel to Instagram. Returns IG post ID."""
    token = settings.INSTAGRAM_ACCESS_TOKEN
    if not token:
        log.error("INSTAGRAM_ACCESS_TOKEN not set in .env")
        return None

    publisher = InstagramPublisher(token)
    log.info("Publishing carousel (%d images) to @%s...", len(image_urls), USERNAME)
    try:
        post_id = publisher.publish_carousel(
            ig_user_id=IG_USER_ID,
            image_urls=image_urls,
            caption=caption,
            hashtags=hashtags,
        )
        log.info("SUCCESS! Instagram post ID: %s", post_id)
        return post_id
    except Exception as e:
        log.error("Publish failed: %s", e)
        return None


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    log.info("=" * 60)
    log.info("AI Creator OS — End-to-End Publish Test")
    log.info("Account: @%s | Niche: %s", USERNAME, NICHE)
    log.info("=" * 60)

    # ── Get account from DB ────────────────────────────────────────────────
    accounts = db.get_active_accounts()
    account = next((a for a in accounts if a["username"] == USERNAME), None)
    if not account:
        log.error("Account '%s' not found in DB. Run setup_accounts.py first.", USERNAME)
        sys.exit(1)
    log.info("Account found: ID=%s", account["account_id"][:8])

    # ── Step 1: Trend ──────────────────────────────────────────────────────
    log.info("\n── STEP 1: Trend Discovery ──────────────────────────────────")
    trend = discover_trend(account)
    if not trend:
        sys.exit(1)

    # ── Step 2: Content creation ───────────────────────────────────────────
    log.info("\n── STEP 2: Content Creation ─────────────────────────────────")
    carousel = create_content(account, trend)
    if not carousel or not carousel.get("slides"):
        log.error("Content creation failed — no slides generated.")
        sys.exit(1)

    slides = carousel["slides"]
    caption = carousel.get("caption", "")
    hashtags = carousel.get("hashtags", [])

    log.info("Caption preview: %s...", caption[:100])
    log.info("Hashtags: %d tags", len(hashtags))

    # Limit to 10 slides (Instagram carousel max)
    if len(slides) > 10:
        slides = slides[:10]
        log.info("Trimmed to 10 slides (Instagram max)")
    if len(slides) < 2:
        log.warning("Only %d slide(s) — adding a CTA slide", len(slides))
        slides.append({"text": f"Follow {HANDLE} for daily AI tips!"})

    # ── Step 3: Generate slide images ──────────────────────────────────────
    log.info("\n── STEP 3: Generating Slide Images ──────────────────────────")
    slide_paths = generate_all_slides(slides)

    # ── Step 4: Upload to catbox.moe ───────────────────────────────────────
    log.info("\n── STEP 4: Uploading Images ─────────────────────────────────")
    image_urls = upload_all_slides(slide_paths)
    if not image_urls:
        log.error("Image upload failed — cannot publish without URLs.")
        sys.exit(1)

    log.info("Uploaded %d images successfully", len(image_urls))

    # ── Save run summary to test/ ──────────────────────────────────────────
    summary = {
        "topic": trend["topic"],
        "hook": carousel.get("slides", [{}])[0].get("text", "")[:200],
        "caption": caption,
        "hashtags": hashtags,
        "image_urls": image_urls,
        "slides_count": len(slides),
    }
    summary_path = OUT_DIR / "run_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    log.info("Summary saved → %s", summary_path)

    # ── Step 5: Publish ────────────────────────────────────────────────────
    log.info("\n── STEP 5: Publishing to Instagram ──────────────────────────")
    post_id = publish(image_urls, caption, hashtags)

    if post_id:
        # Save to DB
        post_record = {
            "account_id": account["account_id"],
            "topic": trend["topic"],
            "hook": carousel.get("slides", [{}])[0].get("text", ""),
            "slides": slides,
            "caption": caption,
            "hashtags": hashtags,
            "image_urls": image_urls,
            "status": "published",
            "instagram_post_id": post_id,
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "content_hash": carousel.get("content_hash", ""),
        }
        try:
            saved = db.create_post(post_record)
            db.update_post(saved["post_id"], {
                "status": "published",
                "instagram_post_id": post_id,
                "posted_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            log.warning("DB save failed (post was published): %s", e)

        db.mark_trend_used(trend["trend_id"])

        log.info("\n" + "=" * 60)
        log.info("POST PUBLISHED SUCCESSFULLY!")
        log.info("Instagram Post ID : %s", post_id)
        log.info("Topic             : %s", trend["topic"][:80])
        log.info("Slides            : %d", len(slides))
        log.info("=" * 60)
    else:
        log.error("\nPublishing failed. Check the logs above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
