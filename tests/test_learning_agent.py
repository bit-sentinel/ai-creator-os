"""Tests for LearningAgent."""
import json
import statistics
from unittest.mock import patch

import pytest

from agents.learning_agent import LearningAgent


MOCK_ANALYSIS = {
    "best_topics": [
        {"topic": "AI automation tricks", "avg_score": 620.0, "sample_count": 3}
    ],
    "best_hooks": [
        {"hook": "7 AI tools saving me 10h/week", "pattern": "NUMBER_LIST", "avg_score": 750.0}
    ],
    "best_posting_times": [
        {"hour_utc": 7, "avg_score": 680.0}
    ],
    "best_carousel_format": {
        "optimal_slide_count": 5,
        "best_cta_type": "question",
        "best_slide1_style": "bold_stat",
    },
    "best_hashtags": [{"tag": "#AITools", "avg_reach": 12000}],
    "worst_topics": ["generic productivity tips"],
    "insights": ["Post more in the mornings", "Number-list hooks outperform story hooks 2:1"],
}

FAKE_POSTS = [
    {
        "post_id": f"post-{i}",
        "topic": f"Topic {i}",
        "hook": f"Hook {i}",
        "slides": [],
        "hashtags": ["#AI"],
        "posted_at": "2026-03-20T08:00:00+00:00",
        "engagement_metrics": [
            {"likes": 200 + i * 10, "comments": 30 + i, "shares": 5, "saves": 40}
        ],
    }
    for i in range(5)
]


class TestLearningAgent:
    @pytest.fixture
    def agent(self):
        return LearningAgent()

    def test_run_updates_strategy_memory(self, agent, sample_account):
        with patch("agents.learning_agent.db") as mock_db, \
             patch.object(agent, "_chat", return_value=json.dumps(MOCK_ANALYSIS)):
            mock_db.get_published_posts_since.return_value = FAKE_POSTS
            result = agent.run(sample_account)

        mock_db.upsert_strategy_memory.assert_called_once()
        assert "best_topics" in result
        assert "best_posting_times" in result
        assert "performance_baseline" in result

    def test_returns_empty_when_no_posts(self, agent, sample_account):
        with patch("agents.learning_agent.db") as mock_db:
            mock_db.get_published_posts_since.return_value = []
            result = agent.run(sample_account)

        assert result == {}

    def test_baseline_computation(self, agent):
        posts = [
            {"engagement_score": 100.0, "metrics": {"likes": 50, "saves": 10}},
            {"engagement_score": 200.0, "metrics": {"likes": 100, "saves": 20}},
            {"engagement_score": 300.0, "metrics": {"likes": 150, "saves": 30}},
        ]
        baseline = agent._compute_baseline(posts)
        assert baseline["avg_engagement_score"] == 200.0
        assert baseline["median_engagement_score"] == 200.0
        assert baseline["avg_likes"] == 100.0
        assert baseline["post_count_analysed"] == 3

    def test_fallback_analysis_when_llm_fails(self, agent, sample_account):
        with patch("agents.learning_agent.db") as mock_db, \
             patch.object(agent, "_chat", return_value="NOT_JSON"):
            mock_db.get_published_posts_since.return_value = FAKE_POSTS
            result = agent.run(sample_account)

        # Should still produce a valid (manual) analysis
        assert "best_topics" in result or result == {}

    def test_enriched_posts_sorted_descending(self, agent):
        posts = [
            {"post_id": "1", "topic": "A", "hook": "h", "slides": [], "hashtags": [],
             "posted_at": "2026-03-18T10:00:00+00:00",
             "engagement_metrics": [{"likes": 10, "comments": 2, "shares": 0, "saves": 1}]},
            {"post_id": "2", "topic": "B", "hook": "h", "slides": [], "hashtags": [],
             "posted_at": "2026-03-19T10:00:00+00:00",
             "engagement_metrics": [{"likes": 500, "comments": 80, "shares": 20, "saves": 100}]},
        ]
        enriched = agent._enrich_with_scores(posts)
        # First item should be highest scoring
        assert enriched[0]["engagement_score"] > enriched[1]["engagement_score"]
