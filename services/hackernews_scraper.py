"""
Hacker News Scraper Service
────────────────────────────
Uses the official HN Firebase REST API (no auth required).
Surfaces top AI-related stories from the last 48 hours.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

HN_API = "https://hacker-news.firebaseio.com/v0"

AI_KEYWORDS = [
    "AI", "GPT", "LLM", "Claude", "Gemini", "OpenAI", "Anthropic",
    "artificial intelligence", "machine learning", "deep learning",
    "neural network", "robot", "automation", "AGI", "ChatGPT",
    "Mistral", "Llama", "Sora", "Midjourney", "Stable Diffusion",
    "self-driving", "autonomous", "computer vision", "transformer",
    "language model", "foundation model", "generative AI", "gen AI",
]


class HackerNewsScraper:
    """Fetches top AI-related stories from Hacker News public API."""

    MAX_SCAN = 200   # How many top story IDs to scan
    POLL_LIMIT = 30  # Max stories to return

    def scrape(self, limit: int = 30) -> List[Dict]:
        """Return up to `limit` AI-related HN stories published in the last 48h."""
        try:
            story_ids = self._get_top_story_ids()
        except Exception as e:
            logger.error("Failed to fetch HN story IDs: %s", e)
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        results: List[Dict] = []

        for sid in story_ids[: self.MAX_SCAN]:
            if len(results) >= limit:
                break
            try:
                story = self._get_story(sid)
                if (
                    story
                    and story.get("type") == "story"
                    and self._is_ai_related(story)
                    and self._is_recent(story, cutoff)
                ):
                    results.append(self._normalise(story))
            except Exception:
                continue

        logger.info("HackerNews: found %d AI-related stories", len(results))
        return results

    # ─── HN Firebase API ─────────────────────────────────────────────────────

    def _get_top_story_ids(self) -> List[int]:
        resp = requests.get(f"{HN_API}/topstories.json", timeout=15)
        resp.raise_for_status()
        return resp.json() or []

    def _get_story(self, story_id: int) -> Optional[Dict]:
        resp = requests.get(f"{HN_API}/item/{story_id}.json", timeout=10)
        resp.raise_for_status()
        return resp.json()

    # ─── Filters ─────────────────────────────────────────────────────────────

    @staticmethod
    def _is_ai_related(story: Dict) -> bool:
        text = f"{story.get('title', '')} {story.get('url', '')}".lower()
        return any(kw.lower() in text for kw in AI_KEYWORDS)

    @staticmethod
    def _is_recent(story: Dict, cutoff: datetime) -> bool:
        ts = story.get("time", 0)
        if not ts:
            return True
        return datetime.fromtimestamp(ts, tz=timezone.utc) >= cutoff

    # ─── Normalisation ───────────────────────────────────────────────────────

    @staticmethod
    def _normalise(story: Dict) -> Dict:
        ts = story.get("time", 0)
        return {
            "title": story.get("title", ""),
            "text": story.get("text", ""),
            "url": story.get("url", ""),
            "author": story.get("by", ""),
            "engagement": {
                "likes": story.get("score", 0),
                "comments": story.get("descendants", 0),
                "shares": 0,
            },
            "published_at": (
                datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else ""
            ),
            "source": "hackernews",
        }
