"""
Test: download the image from a specific LinkedIn post URL by extracting
its Open Graph image tag (publicly accessible for all public posts).
Saves extracted metadata + image to test/ileonjose_anthropic_post/.

Target post:
  https://www.linkedin.com/posts/ileonjose_anthropic-just-dropped-a-new-ai-certification-activity-7441113893092978688-hHBY
"""
import json
import logging
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────
TARGET_POST_URL = (
    "https://www.linkedin.com/posts/ileonjose_anthropic-just-dropped-a-new-ai-"
    "certification-activity-7441113893092978688-hHBY"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "test" / "ileonjose_anthropic_post"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ─── HTML parser: extract <meta> og: tags ────────────────────────────────────
class OGParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.og: Dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        attr_dict = dict(attrs)
        prop = attr_dict.get("property", "") or attr_dict.get("name", "")
        content = attr_dict.get("content", "")
        if prop.startswith("og:") and content:
            self.og[prop[3:]] = content   # strip "og:" prefix


# ─── Helpers ─────────────────────────────────────────────────────────────────
def fetch_og_metadata(post_url: str) -> Dict[str, str]:
    """Fetch the LinkedIn post page and extract Open Graph meta tags."""
    log.info("Fetching post page: %s", post_url)
    try:
        resp = requests.get(post_url, headers=HEADERS, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        log.info("  HTTP %d  (Content-Length: %s bytes)",
                 resp.status_code, resp.headers.get("Content-Length", "?"))
        parser = OGParser()
        parser.feed(resp.text)
        return parser.og
    except Exception as e:
        log.error("Failed to fetch post page: %s", e)
        return {}


def extract_text_from_html(html: str) -> str:
    """Rough extraction of visible post text from page source."""
    # LinkedIn embeds the post text in a <p> inside .share-update-card
    # As a simple fallback, grab the og:description
    return ""


def download_image(url: str, dest: Path) -> bool:
    """Download image from URL to dest. Returns True on success."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/jpeg")
        if dest.suffix == "":
            ext = ".jpg" if "jpeg" in content_type else ".png" if "png" in content_type else ".jpg"
            dest = dest.with_suffix(ext)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        size_kb = dest.stat().st_size // 1024
        log.info("  ✓ Saved %s  (%d KB)", dest.name, size_kb)
        return True
    except Exception as e:
        log.error("  ✗ Download failed (%s): %s", url[:80], e)
        return False


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    og = fetch_og_metadata(TARGET_POST_URL)

    if not og:
        log.error("Could not extract OG metadata. LinkedIn may require auth.")
        sys.exit(1)

    log.info("\n=== Open Graph metadata ===")
    for k, v in og.items():
        log.info("  %-20s %s", k + ":", v[:120])

    # Build a post details dict from OG data
    post_details = {
        "post_url": TARGET_POST_URL,
        "title": og.get("title", ""),
        "description": og.get("description", ""),
        "image_url": og.get("image", "") or og.get("image:url", ""),
        "image_width": og.get("image:width", ""),
        "image_height": og.get("image:height", ""),
        "type": og.get("type", ""),
        "site_name": og.get("site_name", ""),
    }

    image_url = post_details["image_url"]
    if not image_url:
        log.warning("No og:image found in page metadata.")
    else:
        log.info("\nImage URL: %s", image_url)

    # Save output directory
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save metadata
    meta_path = OUT_DIR / "post_details.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(post_details, f, indent=2, ensure_ascii=False)
    log.info("\nMetadata saved → %s", meta_path)

    # Download image
    if image_url:
        raw_path = image_url.split("?")[0]
        ext = Path(raw_path).suffix or ".jpg"
        # strip query-string artefacts like ";base64"
        ext = re.sub(r"[^.a-zA-Z0-9].*", "", ext) or ".jpg"
        dest = OUT_DIR / f"post_image{ext}"
        log.info("\nDownloading image...")
        download_image(image_url, dest)

    # Final summary
    saved_files = sorted(OUT_DIR.iterdir())
    log.info("\n=== Saved to %s ===", OUT_DIR)
    for f in saved_files:
        log.info("  %-30s  %d KB", f.name, f.stat().st_size // 1024)


if __name__ == "__main__":
    main()
