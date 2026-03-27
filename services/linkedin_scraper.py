"""
LinkedIn Scraper Service
─────────────────────────
Uses Apify's LinkedIn Post Search Scraper actor to pull trending posts.
"""
import logging
import random
import time
from typing import Dict, List, Optional

import requests

from config.settings import settings

logger = logging.getLogger(__name__)

APIFY_BASE_URL = "https://api.apify.com/v2"
APiFY_BASE_URL = APIFY_BASE_URL  # alias used by methods

# Niche → curated list of influential LinkedIn profiles to scrape
NICHE_PROFILES: Dict[str, List[str]] = {
    "AI & Productivity": [
        "https://www.linkedin.com/in/satyanadella/",
        "https://www.linkedin.com/in/jeffdean/",
        "https://www.linkedin.com/in/andrewyng/",
        "https://www.linkedin.com/in/garyvaynerchuk/",
        "https://www.linkedin.com/in/reidhoffman/",
    ],
    "Startups & Entrepreneurship": [
        "https://www.linkedin.com/in/reidhoffman/",
        "https://www.linkedin.com/in/garyvaynerchuk/",
        "https://www.linkedin.com/in/tobi/",
        "https://www.linkedin.com/in/jeffweiner08/",
        "https://www.linkedin.com/in/brianschechtman/",
    ],
    "Personal Development & Mindset": [
        "https://www.linkedin.com/in/simon-sinek/",
        "https://www.linkedin.com/in/brenebrownphd/",
        "https://www.linkedin.com/in/adamgrant/",
        "https://www.linkedin.com/in/justinwelsh/",
        "https://www.linkedin.com/in/mattlerner/",
    ],
    "Marketing": [
        "https://www.linkedin.com/in/neilpatel/",
        "https://www.linkedin.com/in/seths/",
        "https://www.linkedin.com/in/garyvaynerchuk/",
    ],
    "Finance": [
        "https://www.linkedin.com/in/ramit-sethi/",
        "https://www.linkedin.com/in/reidhoffman/",
    ],
}

DEFAULT_PROFILES = [
    "https://www.linkedin.com/in/reidhoffman/",
    "https://www.linkedin.com/in/satyanadella/",
]

class LinkedInScraper:
    """Pulls recent posts from niche-relevant LinkedIn profiles via Apify."""

    POLL_INTERVAL = 6    # seconds between run-status polls
    MAX_WAIT = 300       # max seconds to wait for an actor run
    POSTS_PER_PROFILE = 5

    def __init__(self):
        self.token = settings.APIFY_API_TOKEN
        self.actor_id = settings.APIFY_LINKEDIN_ACTOR

    def scrape(self, niche: str, limit: int = 30) -> List[Dict]:
        """
        Scrape recent LinkedIn posts for a niche.
        Rotates across niche-relevant profiles to collect viral content.
        Returns a list of normalised post dicts.
        """
        profiles = NICHE_PROFILES.get(niche, DEFAULT_PROFILES)
        n_profiles = min(len(profiles), max(1, limit // self.POSTS_PER_PROFILE))
        selected = random.sample(profiles, n_profiles)
        logger.info("LinkedIn scrape: niche=%s, profiles=%s", niche, selected)

        all_posts: List[Dict] = []
        for profile_url in selected:
            posts = self._scrape_profile(profile_url, limit=self.POSTS_PER_PROFILE)
            all_posts.extend(posts)
            if len(all_posts) >= limit:
                break

        return all_posts[:limit]

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _scrape_profile(self, profile_url: str, limit: int) -> List[Dict]:
        """Fetch recent posts from one LinkedIn profile."""
        run_id = self._start_run(profile_url, limit)
        if not run_id:
            return []
        dataset_id = self._wait_for_run(run_id)
        if not dataset_id:
            return []
        raw_items = self._fetch_dataset(dataset_id)
        return [self._normalise(item) for item in raw_items if item]

    # ─── Apify API calls ─────────────────────────────────────────────────────

    def _start_run(self, profile_url: str, limit: int) -> Optional[str]:
        slug = self.actor_id.replace("/", "~")
        url = f"{APiFY_BASE_URL}/acts/{slug}/runs"
        payload = {"profileUrl": profile_url, "maxPosts": limit}
        try:
            resp = requests.post(
                url,
                json=payload,
                params={"token": self.token},
                timeout=30,
            )
            resp.raise_for_status()
            run_id = resp.json()["data"]["id"]
            logger.debug("LinkedIn actor run started: %s (profile=%s)", run_id, profile_url)
            return run_id
        except Exception as e:
            logger.error("Failed to start LinkedIn actor for %s: %s", profile_url, e)
            return None

    def _wait_for_run(self, run_id: str) -> Optional[str]:
        url = f"{APiFY_BASE_URL}/actor-runs/{run_id}"
        elapsed = 0
        while elapsed < self.MAX_WAIT:
            try:
                resp = requests.get(url, params={"token": self.token}, timeout=15)
                resp.raise_for_status()
                data = resp.json()["data"]
                status = data.get("status")
                if status == "SUCCEEDED":
                    return data["defaultDatasetId"]
                if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                    logger.error("LinkedIn actor run %s: %s", run_id, status)
                    return None
            except Exception as e:
                logger.warning("Poll error for run %s: %s", run_id, e)

            time.sleep(self.POLL_INTERVAL)
            elapsed += self.POLL_INTERVAL

        logger.error("LinkedIn actor run %s timed out after %ds", run_id, self.MAX_WAIT)
        return None

    def _fetch_dataset(self, dataset_id: str) -> List[Dict]:
        url = f"{APiFY_BASE_URL}/datasets/{dataset_id}/items"
        try:
            resp = requests.get(
                url,
                params={"token": self.token, "format": "json", "limit": 50},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("Failed to fetch LinkedIn dataset %s: %s", dataset_id, e)
            return []

    # ─── Normalization ────────────────────────────────────────────────────────

    @staticmethod
    def _extract_media_urls(media: Optional[Dict]) -> Dict[str, List[str]]:
        """Extract image and video URLs from a media block.

        Observed media.type values:
          "image" / "images" → media.url (canonical), media.images[].url (all sizes)
          "video"            → media.url (MP4 playlist), media.thumbnail (cover image)
        Returns {"image_urls": [...], "video_urls": [...], "thumbnail_urls": [...]}
        """
        if not isinstance(media, dict):
            return {"image_urls": [], "video_urls": [], "thumbnail_urls": []}

        m_type = media.get("type", "")
        image_urls: List[str] = []
        video_urls: List[str] = []
        thumbnail_urls: List[str] = []

        if m_type in ("image", "images"):
            # Collect all available image sizes; prefer media.images list
            for img in media.get("images", []):
                if isinstance(img, dict) and img.get("url"):
                    image_urls.append(img["url"])
            # Fallback: top-level url if images list was empty
            if not image_urls and media.get("url"):
                image_urls.append(media["url"])
        elif m_type == "video":
            if media.get("url"):
                video_urls.append(media["url"])
            if media.get("thumbnail"):
                thumbnail_urls.append(media["thumbnail"])

        return {"image_urls": image_urls, "video_urls": video_urls, "thumbnail_urls": thumbnail_urls}

    @staticmethod
    def _normalise(item: Dict) -> Dict:
        """Map apimaestro/linkedin-profile-posts schema to internal post schema.

        Actual schema (live-inspected):
          author:     {first_name, last_name, headline, username, ...}
          stats:      {total_reactions, like, comments, reposts, ...}
          posted_at:  {date: "YYYY-MM-DD HH:MM:SS", relative, timestamp}
          media:      {type: "image"|"images"|"video", url, images[], thumbnail}
          reshared_post.media: same structure (for quote/repost types)
        """
        stats = item.get("stats", {})
        author = item.get("author", {})
        posted = item.get("posted_at", {})

        if isinstance(author, dict):
            full_name = f"{author.get('first_name', '')} {author.get('last_name', '')}".strip()
            author_name = full_name or author.get("username", "")
        else:
            author_name = str(author)

        published_at = (
            posted.get("date", "") if isinstance(posted, dict) else str(posted)
        )

        # Extract media from top-level field; fall back to reshared_post.media
        media = item.get("media")
        if not media:
            reshared = item.get("reshared_post", {})
            if isinstance(reshared, dict):
                media = reshared.get("media")

        media_data = LinkedInScraper._extract_media_urls(media)

        return {
            "title": item.get("text", "")[:300],
            "text": item.get("text", ""),
            "url": item.get("url", ""),
            "author": author_name,
            "post_type": item.get("post_type", "regular"),
            "engagement": {
                "likes": stats.get("total_reactions", stats.get("like", 0)),
                "comments": stats.get("comments", 0),
                "shares": stats.get("reposts", 0),
            },
            "published_at": published_at,
            "image_urls": media_data["image_urls"],
            "video_urls": media_data["video_urls"],
            "thumbnail_urls": media_data["thumbnail_urls"],
        }

