"""Tests for TrendAgent."""
import json
from unittest.mock import MagicMock, patch

import pytest

from agents.trend_agent import TrendAgent

MOCK_SCORED = [
    {"topic": "AI replaces 80% of office jobs by 2026", "viral_score": 92.0, "reason": "fear and curiosity"},
    {"topic": "5 ChatGPT prompts that triple your output", "viral_score": 88.0, "reason": "actionable"},
    {"topic": "Why remote work is dying", "viral_score": 71.0, "reason": "controversial"},
]

FAKE_LINKEDIN_POSTS = [
    {"title": f"LinkedIn post {i}", "text": f"body {i}", "url": f"https://linkedin.com/{i}",
     "engagement": {"likes": 500 + i * 100}, "source": "linkedin"}
    for i in range(10)
]
FAKE_REDDIT_POSTS = [
    {"title": f"Reddit thread {i}", "text": f"body {i}", "url": f"https://reddit.com/{i}",
     "engagement": {"likes": 1000 + i * 50}, "source": "reddit"}
    for i in range(10)
]


class TestTrendAgent:
    @pytest.fixture
    def agent(self):
        return TrendAgent()

    def test_run_saves_new_trends(self, agent):
        with patch.object(agent.linkedin_scraper, "scrape", return_value=FAKE_LINKEDIN_POSTS), \
             patch.object(agent.reddit_scraper, "scrape", return_value=FAKE_REDDIT_POSTS), \
             patch.object(agent, "_chat", return_value=json.dumps(MOCK_SCORED)), \
             patch("agents.trend_agent.db") as mock_db:

            mock_db.trend_topic_exists.return_value = False
            result = agent.run(niche="AI & Productivity")

        mock_db.save_trends.assert_called_once()
        assert len(result) == 3

    def test_dedup_removes_existing(self, agent):
        with patch.object(agent.linkedin_scraper, "scrape", return_value=FAKE_LINKEDIN_POSTS), \
             patch.object(agent.reddit_scraper, "scrape", return_value=FAKE_REDDIT_POSTS), \
             patch.object(agent, "_chat", return_value=json.dumps(MOCK_SCORED)), \
             patch("agents.trend_agent.db") as mock_db:

            # All topics already exist
            mock_db.trend_topic_exists.return_value = True
            result = agent.run(niche="AI & Productivity")

        assert result == []
        mock_db.save_trends.assert_not_called()

    def test_handles_scraper_failure_gracefully(self, agent):
        with patch.object(agent.linkedin_scraper, "scrape", side_effect=Exception("network error")), \
             patch.object(agent.reddit_scraper, "scrape", return_value=FAKE_REDDIT_POSTS), \
             patch.object(agent, "_chat", return_value=json.dumps(MOCK_SCORED)), \
             patch("agents.trend_agent.db") as mock_db:

            mock_db.trend_topic_exists.return_value = False
            result = agent.run(niche="AI & Productivity")

        # Should still return results from Reddit
        assert len(result) > 0

    def test_returns_empty_when_no_posts(self, agent):
        with patch.object(agent.linkedin_scraper, "scrape", return_value=[]), \
             patch.object(agent.reddit_scraper, "scrape", return_value=[]):

            result = agent.run(niche="AI & Productivity")

        assert result == []
