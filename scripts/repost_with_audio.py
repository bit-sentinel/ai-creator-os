"""
Repost with Text Overlay + Audio
──────────────────────────────────
Takes the most recent published/scheduled post for an account,
adds dramatic text to the image, generates a TTS voiceover,
creates a vertical Reel video, and publishes it to Instagram.

Usage:
    python scripts/repost_with_audio.py --account cognitionlabs.ai
    python scripts/repost_with_audio.py --account cognitionlabs.ai --post-id <uuid>
"""
import argparse
import logging
import os
import sys
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from services.text_overlay import TextOverlayService
from services.audio_generator import AudioGenerator
from services.video_creator import VideoCreator
from services.instagram_publisher import InstagramPublisher
from services import supabase_client as db
from supabase import create_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("repost_with_audio")

SUPABASE_BUCKET = "post-images"


def run(account_username: str, post_id: str = None):
    # ── 1. Load account ───────────────────────────────────────────────────────
    accounts = db.get_active_accounts()
    account = next((a for a in accounts if a["username"] == account_username), None)
    if not account:
        logger.error("Account '%s' not found", account_username)
        sys.exit(1)

    if not account.get("access_token") or not account.get("instagram_user_id"):
        logger.error("Account '%s' missing Instagram credentials", account_username)
        sys.exit(1)

    # ── 2. Load post from DB ──────────────────────────────────────────────────
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    if post_id:
        result = client.table("posts").select("*").eq("post_id", post_id).execute()
    else:
        result = (
            client.table("posts")
            .select("*")
            .eq("account_id", account["account_id"])
            .in_("status", ["published", "scheduled", "failed"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

    if not result.data:
        logger.error("No post found")
        sys.exit(1)

    post = result.data[0]
    slide = post["slides"][0]
    image_url = slide.get("image_url", "")
    hook = post.get("hook", "")
    caption = post.get("caption", "")
    hashtags = post.get("hashtags", [])

    logger.info("Processing post: %s", post["topic"][:70])
    logger.info("Hook: %s", hook[:80])

    if not image_url or image_url.startswith("file://") or "placehold" in image_url:
        logger.error("Post has no valid public image URL: %s", image_url)
        sys.exit(1)

    # ── 3. Download original image locally ───────────────────────────────────
    logger.info("Downloading image from: %s", image_url)
    local_image = f"/tmp/repost_source_{post['post_id'][:8]}.png"
    resp = requests.get(image_url, timeout=30)
    resp.raise_for_status()
    with open(local_image, "wb") as f:
        f.write(resp.content)
    logger.info("Image downloaded: %s", local_image)

    # ── 4. Extract hook lines ─────────────────────────────────────────────────
    lines = [l.strip() for l in hook.strip().split("\n") if l.strip()]
    line1 = lines[0] if len(lines) > 0 else post["topic"][:60]
    line2 = lines[1] if len(lines) > 1 else ""
    line3 = lines[2] if len(lines) > 2 else ""

    # Short overlay text = LINE 1 only (most shocking statement)
    overlay_text = line1

    # ── 5. Add text overlay to image ─────────────────────────────────────────
    logger.info("Adding text overlay: '%s' | watermark: @%s", overlay_text, account_username)
    overlay_service = TextOverlayService()
    overlaid_image = f"/tmp/repost_overlay_{post['post_id'][:8]}.png"
    overlay_service.add_text(
        local_image, overlay_text,
        output_path=overlaid_image,
        username=account_username,
    )

    # ── 6. Upload overlaid image to Supabase Storage ──────────────────────────
    logger.info("Uploading image to Supabase Storage...")
    import uuid as _uuid
    image_filename = f"post_{_uuid.uuid4().hex[:8]}.png"
    storage_key = settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY
    upload_url = f"{settings.SUPABASE_URL}/storage/v1/object/post-images/{image_filename}"
    headers = {
        "Authorization": f"Bearer {storage_key}",
        "Content-Type": "image/png",
        "x-upsert": "true",
    }
    with open(overlaid_image, "rb") as f:
        upload_resp = requests.post(upload_url, headers=headers, data=f, timeout=30)

    if upload_resp.status_code not in (200, 201):
        logger.error("Image upload failed (%s): %s", upload_resp.status_code, upload_resp.text[:200])
        sys.exit(1)

    public_image_url = (
        f"{settings.SUPABASE_URL}/storage/v1/object/public/post-images/{image_filename}"
    )
    logger.info("Image uploaded: %s", public_image_url)

    # ── 7. Publish as single photo post ───────────────────────────────────────
    logger.info("Publishing photo post to @%s...", account_username)
    publisher = InstagramPublisher(account["access_token"])

    ig_post_id = publisher.publish_single_image(
        ig_user_id=account["instagram_user_id"],
        image_url=public_image_url,
        caption=caption,
        hashtags=hashtags,
    )

    logger.info("=" * 60)
    logger.info("REEL PUBLISHED SUCCESSFULLY!")
    logger.info("Instagram Post ID: %s", ig_post_id)
    logger.info("Account: @%s", account_username)
    logger.info("Topic: %s", post["topic"][:70])
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Repost with text overlay and voiceover")
    parser.add_argument("--account", required=True, help="Instagram account username")
    parser.add_argument("--post-id", help="Specific post UUID (optional — defaults to latest)")
    args = parser.parse_args()
    run(args.account, args.post_id)
