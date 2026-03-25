"""
Analytics Agent
───────────────
Fetches engagement metrics from the Instagram Graph API for published posts.
Calculates engagement scores and persists to Supabase.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from agents.base_agent import BaseAgent
from services.instagram_publisher import InstagramPublisher
from services import supabase_client as db

logger = logging.getLogger(__name__)

ENGAGEMENT_SCORE_WEIGHTS = {
    "likes": 1,
    "comments": 3,
    "shares": 5,
    "saves": 4,
}


class AnalyticsAgent(BaseAgent):
    """Collects engagement metrics and computes engagement scores."""

    def __init__(self):
        super().__init__("AnalyticsAgent", temperature=0.1)

    def run(self, account: Dict) -> List[Dict]:
        """
        Fetch metrics for all published posts of an account.
        Saves results to DB and returns a list of metric records.
        """
        account_id = account["account_id"]
        access_token = account.get("access_token")

        if not access_token:
            self.logger.error("No access token for account %s", account_id)
            return []

        self._log_start(f"account={account.get('username')}")

        publisher = InstagramPublisher(access_token)
        posts = db.get_published_posts_since(account_id, days=30)

        if not posts:
            self.logger.info("No published posts found for account %s", account_id)
            return []

        metric_records = []
        for post in posts:
            ig_post_id = post.get("instagram_post_id")
            if not ig_post_id:
                continue
            try:
                raw_metrics = publisher.get_post_insights(ig_post_id)
                record = self._build_metric_record(post["post_id"], raw_metrics)
                metric_records.append(record)
            except Exception as e:
                self.logger.error(
                    "Failed to fetch metrics for post %s: %s",
                    post.get("post_id"), e,
                )

        if metric_records:
            db.save_metrics(metric_records)
            self._log_done(f"Saved metrics for {len(metric_records)} posts")

        return metric_records

    def compute_engagement_score(self, metrics: Dict) -> float:
        """
        Engagement score formula:
          score = likes*1 + comments*3 + shares*5 + saves*4
        """
        return sum(
            metrics.get(metric, 0) * weight
            for metric, weight in ENGAGEMENT_SCORE_WEIGHTS.items()
        )

    # ─── Internal ────────────────────────────────────────────────────────────

    def _build_metric_record(self, post_id: str, raw: Dict) -> Dict:
        return {
            "post_id": post_id,
            "likes": raw.get("like_count", 0),
            "comments": raw.get("comments_count", 0),
            "shares": raw.get("shares", 0),
            "saves": raw.get("saved", 0),
            "reach": raw.get("reach", 0),
            "impressions": raw.get("impressions", 0),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }
