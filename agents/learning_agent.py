"""
Learning & Optimization Agent
──────────────────────────────
Analyses the last 7 days of engagement data and updates strategy_memory.
Future content generation uses this memory to bias toward proven patterns.
"""
import json
import logging
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from agents.base_agent import BaseAgent
from agents.analytics_agent import AnalyticsAgent
from services import supabase_client as db

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """
You are a data-driven Instagram growth strategist.

Given a collection of posts with their engagement scores from the last 7 days,
analyse the patterns and extract actionable optimization insights.

Focus on:
1. Which topic themes drove highest engagement
2. Which hook patterns (question, number list, bold claim, story) performed best
3. Optimal posting times (based on posted_at timestamps)
4. Carousel format patterns that worked best (CTA type, slide 1 style)
5. Which topics or hooks consistently underperformed

Return ONLY valid JSON with this structure:
{
  "best_topics": [{"topic": "...", "avg_score": 123.4, "sample_count": 2}],
  "best_hooks": [{"hook": "...", "pattern": "question|stat|story|list", "avg_score": 99.0}],
  "best_posting_times": [{"hour_utc": 7, "avg_score": 110.2}],
  "best_carousel_format": {
    "optimal_slide_count": 5,
    "best_cta_type": "question",
    "best_slide1_style": "bold_stat"
  },
  "best_hashtags": [{"tag": "#AI", "avg_reach": 5000}],
  "worst_topics": ["..."],
  "insights": ["<actionable sentence 1>", "<actionable sentence 2>"]
}

Do NOT output anything outside the JSON.
"""


class LearningAgent(BaseAgent):
    """Analyses engagement data and updates per-account strategy memory."""

    def __init__(self):
        super().__init__("LearningAgent", temperature=0.2)
        self.analytics = AnalyticsAgent()

    def run(self, account: Dict) -> Dict:
        """
        Run the full learning loop for one account.

        1. Pulls published posts + metrics from the last 7 days
        2. Computes engagement scores
        3. Sends to LLM for pattern analysis
        4. Updates strategy_memory in DB
        Returns the new strategy memory dict.
        """
        account_id = account["account_id"]
        self._log_start(f"account={account.get('username')}")

        posts = db.get_published_posts_since(account_id, days=7)
        if not posts:
            self.logger.info("No posts to learn from for account %s", account_id)
            return {}

        enriched = self._enrich_with_scores(posts)
        if not enriched:
            self.logger.info("No scored posts for account %s", account_id)
            return {}

        new_memory = self._analyse_with_llm(enriched)
        new_memory["performance_baseline"] = self._compute_baseline(enriched)

        db.upsert_strategy_memory(account_id, new_memory)
        self._log_done(f"Strategy memory updated for {account.get('username')}")
        return new_memory

    # ─── Internals ───────────────────────────────────────────────────────────

    def _enrich_with_scores(self, posts: List[Dict]) -> List[Dict]:
        """Attach computed engagement scores to each post."""
        enriched = []
        for post in posts:
            metrics_list = post.get("engagement_metrics", [])
            # Use most recent metric snapshot
            metrics = metrics_list[-1] if metrics_list else {}
            score = self.analytics.compute_engagement_score(metrics)
            enriched.append({
                "post_id": post["post_id"],
                "topic": post.get("topic", ""),
                "hook": post.get("hook", ""),
                "slides": post.get("slides", []),
                "hashtags": post.get("hashtags", []),
                "posted_at": post.get("posted_at", ""),
                "engagement_score": score,
                "metrics": metrics,
            })
        return sorted(enriched, key=lambda x: x["engagement_score"], reverse=True)

    def _analyse_with_llm(self, posts: List[Dict]) -> Dict:
        """Send enriched posts to LLM for strategic analysis."""
        # Summarise to keep tokens manageable
        summaries = [
            {
                "topic": p["topic"][:150],
                "hook": p["hook"][:120],
                "engagement_score": round(p["engagement_score"], 1),
                "metrics": {k: p["metrics"].get(k, 0) for k in ["likes", "comments", "shares", "saves"]},
                "posted_at": p.get("posted_at", ""),
                "hashtags": p.get("hashtags", [])[:10],
            }
            for p in posts[:30]  # cap at 30 posts
        ]

        user_prompt = (
            f"Posts (sorted by engagement score, high to low):\n"
            f"{json.dumps(summaries, indent=2)}"
        )

        try:
            analysis = self._chat_json(ANALYSIS_SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            self.logger.error("Learning analysis parse error: %s", e)
            analysis = self._manual_analysis(posts)

        return analysis

    def _compute_baseline(self, posts: List[Dict]) -> Dict:
        """Compute average performance metrics as a baseline."""
        if not posts:
            return {}
        scores = [p["engagement_score"] for p in posts]
        likes = [p["metrics"].get("likes", 0) for p in posts]
        saves = [p["metrics"].get("saves", 0) for p in posts]
        return {
            "avg_engagement_score": round(statistics.mean(scores), 2),
            "median_engagement_score": round(statistics.median(scores), 2),
            "avg_likes": round(statistics.mean(likes), 1),
            "avg_saves": round(statistics.mean(saves), 1),
            "post_count_analysed": len(posts),
            "analysis_date": datetime.now(timezone.utc).isoformat(),
        }

    def _manual_analysis(self, posts: List[Dict]) -> Dict:
        """Fallback rule-based analysis when LLM parsing fails."""
        top = posts[:3]
        bottom = posts[-3:] if len(posts) >= 6 else []

        # Extract hour from posted_at
        time_scores: Dict[int, List[float]] = defaultdict(list)
        for p in posts:
            try:
                hour = datetime.fromisoformat(p["posted_at"]).hour
                time_scores[hour].append(p["engagement_score"])
            except Exception:
                pass

        best_times = sorted(
            [{"hour_utc": h, "avg_score": round(statistics.mean(s), 2)} for h, s in time_scores.items()],
            key=lambda x: x["avg_score"],
            reverse=True,
        )[:3]

        return {
            "best_topics": [{"topic": p["topic"][:100], "avg_score": p["engagement_score"], "sample_count": 1} for p in top],
            "best_hooks": [{"hook": p["hook"][:100], "pattern": "unknown", "avg_score": p["engagement_score"]} for p in top],
            "best_posting_times": best_times,
            "best_carousel_format": {"optimal_slide_count": 5},
            "best_hashtags": [],
            "worst_topics": [p["topic"][:100] for p in bottom],
            "insights": ["Increase posting frequency during peak hours", "Replicate top-performing topic themes"],
        }
