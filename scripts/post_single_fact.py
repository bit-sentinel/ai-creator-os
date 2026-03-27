"""
Single-Image Fact Post Publisher
──────────────────────────────────
Generates one branded fact post following the exact style rules:
- Curiosity-driven hook + surprising AI/tech insight
- 2–3 short sentences, readable as overlay text
- Modern dark-gradient card design (viral edtech Instagram style)
- Published as a single-image post to @1min_ai_lessons

Usage:
  python scripts/post_single_fact.py
"""

import json
import logging
import math
import random
import sys
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()

from config.settings import settings
from services.instagram_publisher import InstagramPublisher
from services import supabase_client as db

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fact_post")

# ─── Config ───────────────────────────────────────────────────────────────────
USERNAME   = "1min_ai_lessons"
IG_USER_ID = "26478207988482384"
NICHE      = "AI & Productivity"
HANDLE     = "@1min_ai_lessons"

SIZE = (1080, 1080)
OUT_DIR = Path(__file__).resolve().parent.parent / "test" / "single_fact_post"

# Font search paths (macOS)
FONT_PATHS = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Arial.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/SFNS.ttf",
    "/System/Library/Fonts/SFNSDisplay.ttf",
    "/System/Library/Fonts/SFCompact.ttf",
]

# Color palettes for variety — each is (bg_start, bg_end, accent, text)
PALETTES = [
    # Purple → Black (default AI vibe)
    ((20, 10, 45), (5, 5, 20), (139, 92, 246), (255, 255, 255)),
    # Deep Blue → Navy
    ((10, 20, 60), (5, 10, 30), (59, 130, 246), (255, 255, 255)),
    # Teal → Dark
    ((5, 35, 45), (3, 15, 20), (20, 184, 166), (255, 255, 255)),
    # Dark Red → Black
    ((40, 10, 10), (15, 5, 5), (239, 68, 68), (255, 255, 255)),
    # Emerald → Dark
    ((5, 40, 25), (3, 18, 12), (16, 185, 129), (255, 255, 255)),
]

STYLE_PROMPT = """You are a viral AI education content creator for Instagram (@1min_ai_lessons).

Generate ONE educational fact post following these EXACT rules:

POST FORMAT:
- Line 1: A hook emoji + short punchy hook sentence (max 10 words, must spark curiosity)
- Line 2: The surprising fact or insight (1–2 sentences, max 25 words total)
- Line 3: A call-to-action or follow-up thought (max 10 words)

CONTENT RULES:
- Must reveal a surprising or little-known insight about AI/tech
- Topic categories: AI Tools, Artificial Intelligence, Productivity Hacks, Tech Tips, Future of Work
- Tone: fascinating, insightful, curiosity-driven — NOT corporate or preachy
- Total text: 2–3 short sentences maximum
- Must be readable as overlay text on a dark image
- No hashtags in the text itself
- No long explanations

CAPTION RULES (separate from post text):
- 3–5 sentences expanding on the insight
- End with a question to drive comments
- Conversational, not corporate

Respond in this EXACT JSON format (no markdown fences):
{
  "hook": "🤖 Most people don't know this about ChatGPT",
  "fact": "OpenAI's GPT-4 was trained on roughly 1 trillion tokens — equivalent to reading every book ever written 1,000 times.",
  "cta": "Save this before they change it 👇",
  "caption": "OpenAI's models are trained on datasets so massive they're hard to comprehend...",
  "hashtags": ["#AIFacts", "#ChatGPT", "#ArtificialIntelligence", "#TechTips", "#FutureOfWork", "#AITools", "#MachineLearning", "#ProductivityHacks", "#TechEducation", "#AILearning", "#DigitalTransformation", "#TechInnovation", "#AIMarketing", "#DeepLearning", "#TechTrends", "#Innovation", "#StartupLife", "#Entrepreneur", "#BusinessGrowth", "#Technology", "#Programming", "#DataScience", "#Python", "#WebDev", "#Coding", "#LearnAI", "#EdTech", "#Growth", "#Mindset", "#Success"]
}"""


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — GENERATE CONTENT WITH CLAUDE
# ═══════════════════════════════════════════════════════════════════════════════

def generate_fact() -> dict:
    """Call Claude directly with style rules to generate the fact post content."""
    import anthropic
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    log.info("Generating fact post with Claude...")
    msg = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": STYLE_PROMPT}],
    )
    raw = msg.content[0].text.strip()

    # Strip JSON fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    data = json.loads(raw)
    log.info("Hook: %s", data.get("hook", "")[:80])
    log.info("Fact: %s", data.get("fact", "")[:100])
    return data


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — GENERATE BRANDED IMAGE
# ═══════════════════════════════════════════════════════════════════════════════

def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _gradient_background(size: Tuple[int, int], c1: Tuple, c2: Tuple) -> Image.Image:
    """Create a smooth diagonal gradient background."""
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    w, h = size
    for y in range(h):
        t = y / h
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def _draw_noise_texture(img: Image.Image, intensity: int = 8) -> Image.Image:
    """Add very subtle grain texture for depth."""
    import random as _r
    pixels = img.load()
    w, h = img.size
    for _ in range(w * h // 20):   # sparse — 5% of pixels
        x = _r.randint(0, w - 1)
        y = _r.randint(0, h - 1)
        r, g, b = pixels[x, y]
        d = _r.randint(-intensity, intensity)
        pixels[x, y] = (
            max(0, min(255, r + d)),
            max(0, min(255, g + d)),
            max(0, min(255, b + d)),
        )
    return img


def _draw_geometric_bg(draw: ImageDraw.ImageDraw, accent: Tuple, size: Tuple):
    """Draw subtle decorative circles and lines for the modern tech look."""
    w, h = size
    # Large faint circle (top-right)
    cx, cy, r = int(w * 0.85), int(h * 0.15), 320
    for thickness in range(0, 3):
        draw.ellipse(
            [cx - r + thickness, cy - r + thickness,
             cx + r - thickness, cy + r - thickness],
            outline=(*accent, 18),
        )
    # Small accent circle (bottom-left)
    cx2, cy2, r2 = int(w * 0.12), int(h * 0.88), 140
    draw.ellipse(
        [cx2 - r2, cy2 - r2, cx2 + r2, cy2 + r2],
        outline=(*accent, 30),
    )
    # Horizontal accent line (top area)
    draw.rectangle([80, 178, 80 + 60, 182], fill=accent)
    # Subtle dot grid (top-left corner)
    for gx in range(80, 220, 22):
        for gy in range(80, 160, 22):
            draw.ellipse([gx, gy, gx + 3, gy + 3], fill=(*accent, 40))


def _wrap_text(draw, text: str, font, max_width: int) -> list:
    """Word-wrap text into lines fitting max_width."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_text_block(
    draw, lines: list, font, color: Tuple,
    x: int, start_y: int, line_gap: int = 14,
) -> int:
    """Draw a list of lines. Returns y after last line."""
    y = start_y
    for line in lines:
        draw.text((x, y), line, font=font, fill=color)
        bbox = draw.textbbox((x, y), line, font=font)
        y += (bbox[3] - bbox[1]) + line_gap
    return y


def generate_image(hook: str, fact: str, cta: str, palette_idx: int = 0) -> Path:
    """Generate and save the 1080x1080 post image. Returns saved path."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    bg_start, bg_end, accent, text_color = PALETTES[palette_idx % len(PALETTES)]
    subtext_color = tuple(min(255, c + 90) for c in bg_start)  # lighter version of bg

    # ── Base gradient ────────────────────────────────────────────────────
    img = _gradient_background(SIZE, bg_start, bg_end)
    img = _draw_noise_texture(img, 6)

    # Convert accent to RGBA for transparent drawing
    draw = ImageDraw.Draw(img, "RGBA")

    # ── Geometric decoration ─────────────────────────────────────────────
    _draw_geometric_bg(draw, accent, SIZE)

    # Switch back to RGB draw for text
    draw = ImageDraw.Draw(img)

    # ── Top bar: logo area ───────────────────────────────────────────────
    draw.rectangle([0, 0, 6, 1080], fill=accent)          # left accent strip

    # "AI FACTS" badge
    badge_font = _font(26)
    badge_text = "A I  L E S S O N S"
    draw.text((80, 66), badge_text, font=badge_font, fill=accent)

    # ── Hook text ────────────────────────────────────────────────────────
    hook_font = _font(62)
    margin = 80
    max_w = SIZE[0] - margin * 2
    hook_lines = _wrap_text(draw, hook, hook_font, max_w)

    y = 220
    y = _draw_text_block(draw, hook_lines, hook_font, text_color, margin, y, line_gap=16)

    # ── Divider ─────────────────────────────────────────────────────────
    y += 28
    draw.rectangle([margin, y, margin + 80, y + 4], fill=accent)
    y += 36

    # ── Fact text ────────────────────────────────────────────────────────
    fact_font = _font(44)
    fact_lines = _wrap_text(draw, fact, fact_font, max_w)
    subtext_col = tuple(min(255, c + 120) for c in bg_end)
    y = _draw_text_block(draw, fact_lines, fact_font, (220, 220, 235), margin, y, line_gap=18)

    # ── CTA text ─────────────────────────────────────────────────────────
    y += 36
    cta_font = _font(38)
    cta_lines = _wrap_text(draw, cta, cta_font, max_w)
    y = _draw_text_block(draw, cta_lines, cta_font, accent, margin, y, line_gap=14)

    # ── Bottom bar ───────────────────────────────────────────────────────
    draw.rectangle([0, 1030, 1080, 1080], fill=(*bg_start, 200))
    draw.rectangle([0, 1028, 1080, 1032], fill=(*accent, 160))

    # Handle + follow prompt
    handle_font = _font(30)
    draw.text((margin, 1044), HANDLE, font=handle_font, fill=accent)
    follow_text = "Follow for daily AI insights"
    follow_font = _font(26)
    fw = draw.textbbox((0, 0), follow_text, font=follow_font)[2]
    draw.text((SIZE[0] - fw - margin, 1048), follow_text,
              font=follow_font, fill=(170, 170, 190))

    # ── Save ─────────────────────────────────────────────────────────────
    out_path = OUT_DIR / "post_image.jpg"
    img.save(out_path, "JPEG", quality=95)
    log.info("Image saved: %s", out_path)
    return out_path


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — UPLOAD + PUBLISH
# ═══════════════════════════════════════════════════════════════════════════════

def upload_to_catbox(path: Path) -> Optional[str]:
    log.info("Uploading image to catbox.moe...")
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
            log.info("Uploaded → %s", url)
            return url
        log.error("catbox returned: %s", url[:80])
        return None
    except Exception as e:
        log.error("Upload failed: %s", e)
        return None


def publish_single_image(image_url: str, caption: str, hashtags: list) -> Optional[str]:
    """Publish a single-image post (not carousel) to Instagram."""
    token = settings.INSTAGRAM_ACCESS_TOKEN
    if not token:
        log.error("INSTAGRAM_ACCESS_TOKEN not set")
        return None

    from services.instagram_publisher import GRAPH_BASE
    import time

    full_caption = caption + "\n\n.\n.\n.\n" + " ".join(hashtags[:30])

    # Create single-image container
    log.info("Creating image container...")
    resp = requests.post(
        f"{GRAPH_BASE}/{IG_USER_ID}/media",
        params={
            "image_url": image_url,
            "caption": full_caption[:2200],
            "access_token": token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    container_id = resp.json()["id"]
    log.info("Container created: %s", container_id)

    # Poll until ready
    log.info("Waiting for container to be ready...")
    for _ in range(20):
        time.sleep(4)
        r = requests.get(
            f"{GRAPH_BASE}/{container_id}",
            params={"fields": "status_code", "access_token": token},
            timeout=15,
        )
        status = r.json().get("status_code", "")
        log.info("  Container status: %s", status)
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Container failed: {status}")

    # Publish
    log.info("Publishing...")
    resp2 = requests.post(
        f"{GRAPH_BASE}/{IG_USER_ID}/media_publish",
        params={"creation_id": container_id, "access_token": token},
        timeout=30,
    )
    resp2.raise_for_status()
    post_id = resp2.json()["id"]
    log.info("Published! Post ID: %s", post_id)
    return post_id


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("=" * 60)
    log.info("Single Fact Post — @%s", USERNAME)
    log.info("=" * 60)

    # ── Step 1: Generate content ────────────────────────────────────────
    log.info("\n── STEP 1: Generating content...")
    data = generate_fact()

    hook     = data["hook"]
    fact     = data["fact"]
    cta      = data["cta"]
    caption  = data["caption"]
    hashtags = data.get("hashtags", [])

    # ── Step 2: Generate image ───────────────────────────────────────────
    log.info("\n── STEP 2: Generating image...")
    palette_idx = random.randint(0, len(PALETTES) - 1)
    img_path = generate_image(hook, fact, cta, palette_idx)

    # Save content preview
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "post_content.json", "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # ── Step 3: Upload ───────────────────────────────────────────────────
    log.info("\n── STEP 3: Uploading image...")
    image_url = upload_to_catbox(img_path)
    if not image_url:
        log.error("Upload failed — cannot publish.")
        sys.exit(1)

    # ── Step 4: Publish ──────────────────────────────────────────────────
    log.info("\n── STEP 4: Publishing to Instagram...")
    post_id = publish_single_image(image_url, caption, hashtags)

    if post_id:
        # Save to DB
        accounts = db.get_active_accounts()
        account = next((a for a in accounts if a["username"] == USERNAME), None)
        if account:
            try:
                from datetime import datetime, timezone
                post_record = {
                    "account_id": account["account_id"],
                    "topic": hook,
                    "hook": hook,
                    "slides": [{"text": hook}, {"text": fact}, {"text": cta}],
                    "caption": caption,
                    "hashtags": hashtags,
                    "image_urls": [image_url],
                    "status": "published",
                    "instagram_post_id": post_id,
                    "scheduled_at": datetime.now(timezone.utc).isoformat(),
                    "content_hash": str(hash(hook + fact)),
                }
                saved = db.create_post(post_record)
                db.update_post(saved["post_id"], {
                    "status": "published",
                    "instagram_post_id": post_id,
                    "posted_at": datetime.now(timezone.utc).isoformat(),
                })
                log.info("Saved to DB: %s", saved["post_id"][:8])
            except Exception as e:
                log.warning("DB save failed (post was published): %s", e)

        log.info("\n" + "=" * 60)
        log.info("POST PUBLISHED SUCCESSFULLY!")
        log.info("Instagram Post ID : %s", post_id)
        log.info("Hook              : %s", hook)
        log.info("=" * 60)
    else:
        log.error("Publish failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
