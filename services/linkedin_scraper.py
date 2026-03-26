"""
LinkedIn Scraper Service
─────────────────────────
Uses Apify's LinkedIn Post Search Scraper actor to pull trending posts.
"""
import logging
import time
from typing import Dict, List, Optional

import requests

from config.settings import settings

logger = logging.getLogger(__name__)

APIFY_BASE_URL = "https://api.apify.com/v2"


class LinkedInScraper:
    """Wraps the Apify LinkedIn scraper actor."""

    POLL_INTERVAL = 5   # seconds between run-status polls
    MAX_WAIT = 300      # max seconds to wait for actor run

    def __init__(self):
        self.token = settings.APIFY_API_TOKEN
        self.actor_id = settings.APIFY_LINKEDIN_ACTOR

    def scrape(self, niche: str, limit: int = 30) -> List[Dict]:
        """
        Scrape recent LinkedIn posts for a niche.
        Returns a list of normalised post dicts.
        """
        keywords = self._niche_to_keywords(niche)
        logger.info("LinkedIn scrape: niche=%s, keywords=%s", niche, keywords)

        run_id = self._start_run(keywords, limit)
        if not run_id:
            return []

        dataset_id = self._wait_for_run(run_id)
        if not dataset_id:
            return []

        raw_items = self._fetch_dataset(dataset_id)
        return [self._normalise(item) for item in raw_items if item]

    # ─── Apify API calls ─────────────────────────────────────────────────────

    def _start_run(self, keywords: List[str], limit: int) -> Optional[str]:
        url = f"{APIFY_BASE_URL}/acts/{self.actor_id.replace('/', '~')}/runs"
        payload = {
            "searchTerms": keywords,
            "maxResults": limit,
            "sort": "RECENT",            # get fresh content
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
            logger.debug("LinkedIn actor run started: %s", run_id)
            return run_id
        except Exception as e:
            logger.error("Failed to start LinkedIn actor: %s", e)
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
                    logger.error("LinkedIn actor run %s: %s", run_id, status)
                    return None
            except Exception as e:
                logger.warning("Poll error for run %s: %s", run_id, e)

            time.sleep(self.POLL_INTERVAL)
            elapsed += self.POLL_INTERVAL

        logger.error("LinkedIn actor run %s timed out after %ds", run_id, self.MAX_WAIT)
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
            logger.error("Failed to fetch LinkedIn dataset %s: %s", dataset_id, e)
            return []

    # ─── Normalization ────────────────────────────────────────────────────────

    @staticmethod
    def _normalise(item: Dict) -> Dict:
        """Map Apify LinkedIn schema to internal post schema."""
        return {
            "title": item.get("text", "")[:300],
            "text": item.get("text", ""),
            "url": item.get("url", item.get("postUrl", "")),
            "author": item.get("author", {}).get("name", ""),
            "engagement": {
                "likes": item.get("likesCount", 0),
                "comments": item.get("commentsCount", 0),
                "shares": item.get("sharesCount", 0),
            },
            "published_at": item.get("postedAt", ""),
        }

    @staticmethod
    def _niche_to_keywords(niche: str) -> List[str]:
        """Convert a niche string to a set of search keywords."""
        keyword_map = {
            "AI & Productivity": ["artificial intelligence productivity", "AI tools 2024", "ChatGPT workflow"],
            "Startups & Entrepreneurship": ["startup growth", "founder lessons", "venture capital"],
            "Personal Development & Mindset": ["mindset growth", "self improvement habits", "discipline"],
            "Marketing": ["digital marketing growth", "content marketing", "social media strategy"],
            "Finance": ["personal finance tips", "investing strategies", "financial freedom"],
        }
        return keyword_map.get(niche, [niche, f"{niche} tips", f"{niche} 2024"])
