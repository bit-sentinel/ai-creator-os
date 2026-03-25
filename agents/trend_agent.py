"""
Trend Discovery Agent
─────────────────────
1. Pulls raw posts from LinkedIn and Reddit via Apify
2. Uses an LLM to score each item for viral potential
3. Deduplicates against existing DB trends
4. Persists ranked trends to Supabase
"""
import hashlib
import json
import logging
from typing import Dict, List, Optional

from agents.base_agent import BaseAgent
from services.linkedin_scraper import LinkedInScraper
from services.reddit_scraper import RedditScraper
from services import supabase_client as db

logger = logging.getLogger(__name__)

SCORE_SYSTEM_PROMPT = """
You are a viral content analyst specialising in social media trends.
Given a list of recent posts, score each one for its viral potential on Instagram
on a scale of 0–100 based on:
  - Emotional resonance (curiosity, surprise, fear-of-missing-out)
  - Shareability
  - Educational or entertainment value
  - Broad audience appeal

Return ONLY a valid JSON array. Each element must have:
  {
    "topic": "<concise 3-10 word topic title>",
    "viral_score": <0-100 float>,
    "reason": "<one sentence why>"
  }

Do NOT include any text outside the JSON array.
"""


class TrendAgent(BaseAgent):
    """Discovers and ranks trends from LinkedIn and Reddit."""

    def __init__(self):
        super().__init__("TrendAgent", temperature=0.3)
        self.linkedin_scraper = LinkedInScraper()
        self.reddit_scraper = RedditScraper()

    # ─── Public interface ────────────────────────────────────────────────────

    def run(self, niche: str, account_id: Optional[str] = None) -> List[Dict]:
        """
        Discover trends for a given niche.

        Returns a list of trend dicts saved to the database.
        """
        self._log_start(f"niche={niche}")

        raw_posts = self._collect_raw_posts(niche)
        if not raw_posts:
            self.logger.warning("No raw posts collected for niche: %s", niche)
            return []

        scored = self._score_trends(raw_posts, niche)
        deduped = self._deduplicate(scored, niche)

        if deduped:
            db.save_trends(deduped)
            self._log_done(f"Saved {len(deduped)} new trends for '{niche}'")
        else:
            self.logger.info("All discovered trends were duplicates for niche: %s", niche)

        return deduped

    # ─── Internal steps ──────────────────────────────────────────────────────

    def _collect_raw_posts(self, niche: str) -> List[Dict]:
        """Collect raw posts from all sources concurrently."""
        posts = []
        try:
            linkedin_posts = self.linkedin_scraper.scrape(niche, limit=30)
            posts.extend([{**p, "source": "linkedin"} for p in linkedin_posts])
            self.logger.info("LinkedIn: collected %d posts", len(linkedin_posts))
        except Exception as e:
            self.logger.error("LinkedIn scraping failed: %s", e)

        try:
            reddit_posts = self.reddit_scraper.scrape(niche, limit=30)
            posts.extend([{**p, "source": "reddit"} for p in reddit_posts])
            self.logger.info("Reddit: collected %d posts", len(reddit_posts))
        except Exception as e:
            self.logger.error("Reddit scraping failed: %s", e)

        return posts

    def _score_trends(self, posts: List[Dict], niche: str) -> List[Dict]:
        """Use LLM to score each post for viral potential."""
        # Build a condensed representation for the LLM (avoid huge token bills)
        summaries = []
        for i, post in enumerate(posts[:50]):  # cap at 50 to limit tokens
            summaries.append({
                "id": i,
                "title": post.get("title", "")[:200],
                "text": post.get("text", "")[:300],
                "engagement": post.get("engagement", {}),
                "source": post.get("source", ""),
            })

        user_prompt = (
            f"Niche: {niche}\n\n"
            f"Posts to analyse:\n{json.dumps(summaries, indent=2)}"
        )

        try:
            raw = self._chat(SCORE_SYSTEM_PROMPT, user_prompt)
            scored_items = json.loads(raw)
        except (json.JSONDecodeError, Exception) as e:
            self.logger.error("LLM scoring failed: %s", e)
            # Fallback: assign score 50 to all
            scored_items = [
                {"topic": p.get("title", "Unknown")[:100], "viral_score": 50.0, "reason": "fallback"}
                for p in posts[:10]
            ]

        # Hydrate with source metadata
        trend_records = []
        for item in scored_items:
            # Find the best-matching source post by title overlap; default to post 0
            matched = next(
                (s for s in summaries
                 if s.get("title", "")[:50] in item.get("topic", "")
                 or item.get("topic", "") in s.get("title", "")[:200]),
                None,
            )
            idx = matched["id"] if matched else 0
            source_post = posts[min(idx, len(posts) - 1)] if posts else {}

            trend_records.append({
                "platform": source_post.get("source", "unknown"),
                "topic": item["topic"][:500],
                "source_url": source_post.get("url", ""),
                "viral_score": float(item.get("viral_score", 50)),
                "niche": niche,
                "raw_data": {
                    "reason": item.get("reason", ""),
                    "original_title": source_post.get("title", ""),
                    "engagement": source_post.get("engagement", {}),
                },
                "used": False,
            })

        return trend_records

    def _deduplicate(self, trends: List[Dict], niche: str) -> List[Dict]:
        """Remove trends whose topic is too similar to existing DB entries."""
        new_trends = []
        for trend in trends:
            try:
                if not db.trend_topic_exists(trend["topic"]):
                    new_trends.append(trend)
                else:
                    self.logger.debug("Duplicate trend skipped: %s", trend["topic"][:60])
            except Exception as e:
                # If dedup check fails, include the trend (safe fallback)
                self.logger.warning("Dedup check error for '%s': %s", trend["topic"][:60], e)
                new_trends.append(trend)
        return new_trends
