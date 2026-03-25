"""
Reddit Scraper Service
───────────────────────
Uses Apify's Reddit Scraper actor to surface viral threads.
"""
import logging
import time
from typing import Dict, List, Optional

import requests

from config.settings import settings

logger = logging.getLogger(__name__)

APIFY_BASE_URL = "https://api.apify.com/v2"

# Map niches to relevant subreddits
NICHE_SUBREDDITS: Dict[str, List[str]] = {
    "AI & Productivity": [
        "r/artificial", "r/MachineLearning", "r/ChatGPT",
        "r/productivity", "r/selfimprovement",
    ],
    "Startups & Entrepreneurship": [
        "r/startups", "r/Entrepreneur", "r/smallbusiness",
        "r/SideProject", "r/EntrepreneurRideAlong",
    ],
    "Personal Development & Mindset": [
        "r/selfimprovement", "r/getdisciplined", "r/decidingtobebetter",
        "r/MindfulLiving", "r/motivation",
    ],
    "Marketing": [
        "r/marketing", "r/digital_marketing", "r/socialmedia",
        "r/content_marketing", "r/SEO",
    ],
    "Finance": [
        "r/personalfinance", "r/financialindependence", "r/investing",
        "r/stocks", "r/Fire",
    ],
}


class RedditScraper:
    """Wraps the Apify Reddit scraper actor."""

    POLL_INTERVAL = 5
    MAX_WAIT = 300

    def __init__(self):
        self.token = settings.APIFY_API_TOKEN
        self.actor_id = settings.APIFY_REDDIT_ACTOR

    def scrape(self, niche: str, limit: int = 30) -> List[Dict]:
        """Scrape viral Reddit threads for a niche."""
        subreddits = NICHE_SUBREDDITS.get(niche, [f"r/{niche.replace(' ', '').lower()}"])
        logger.info("Reddit scrape: niche=%s, subreddits=%s", niche, subreddits[:3])

        run_id = self._start_run(subreddits, limit)
        if not run_id:
            return []

        dataset_id = self._wait_for_run(run_id)
        if not dataset_id:
            return []

        raw_items = self._fetch_dataset(dataset_id)
        return [self._normalise(item) for item in raw_items if item]

    # ─── Apify API ────────────────────────────────────────────────────────────

    def _start_run(self, subreddits: List[str], limit: int) -> Optional[str]:
        url = f"{APIFY_BASE_URL}/acts/{self.actor_id}/runs"
        payload = {
            "startUrls": [
                {"url": f"https://www.reddit.com/{sr}/top/?t=week"}
                for sr in subreddits[:5]   # Limit to 5 subreddits per run
            ],
            "maxPostCount": limit,
            "skipComments": True,
        }
        try:
            resp = requests.post(
                url,
                json=payload,
                params={"token": self.token},
                timeout=30,
            )
            resp.raise_for_status()
            run_id = resp.json()["data"]["id"]
            logger.debug("Reddit actor run started: %s", run_id)
            return run_id
        except Exception as e:
            logger.error("Failed to start Reddit actor: %s", e)
            return None

    def _wait_for_run(self, run_id: str) -> Optional[str]:
        url = f"{APIFY_BASE_URL}/actor-runs/{run_id}"
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
                    logger.error("Reddit actor run %s: %s", run_id, status)
                    return None
            except Exception as e:
                logger.warning("Poll error: %s", e)

            time.sleep(self.POLL_INTERVAL)
            elapsed += self.POLL_INTERVAL

        logger.error("Reddit actor run %s timed out", run_id)
        return None

    def _fetch_dataset(self, dataset_id: str) -> List[Dict]:
        url = f"{APIFY_BASE_URL}/datasets/{dataset_id}/items"
        try:
            resp = requests.get(
                url,
                params={"token": self.token, "format": "json", "limit": 50},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("Failed to fetch Reddit dataset %s: %s", dataset_id, e)
            return []

    # ─── Normalization ────────────────────────────────────────────────────────

    @staticmethod
    def _normalise(item: Dict) -> Dict:
        return {
            "title": item.get("title", ""),
            "text": item.get("body", item.get("selftext", "")),
            "url": item.get("url", ""),
            "author": item.get("author", ""),
            "engagement": {
                "likes": item.get("score", item.get("ups", 0)),
                "comments": item.get("numComments", item.get("num_comments", 0)),
                "shares": 0,    # Reddit doesn't expose share count
            },
            "published_at": item.get("createdAt", ""),
            "subreddit": item.get("subreddit", ""),
        }
