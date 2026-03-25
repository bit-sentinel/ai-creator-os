"""Tests for AnalyticsAgent."""
from unittest.mock import MagicMock, patch

import pytest

from agents.analytics_agent import AnalyticsAgent, ENGAGEMENT_SCORE_WEIGHTS


class TestEngagementScore:
    def setup_method(self):
        self.agent = AnalyticsAgent()

    def test_zero_metrics(self):
        assert self.agent.compute_engagement_score({}) == 0.0

    def test_formula_correctness(self):
        metrics = {"likes": 100, "comments": 20, "shares": 5, "saves": 10}
        expected = 100 * 1 + 20 * 3 + 5 * 5 + 10 * 4
        assert self.agent.compute_engagement_score(metrics) == expected

    def test_saves_weighted_higher_than_likes(self):
        """One save should be worth more than one like."""
        save_score = self.agent.compute_engagement_score({"saves": 1})
        like_score = self.agent.compute_engagement_score({"likes": 1})
        assert save_score > like_score

    def test_shares_highest_weight(self):
        """One share should score higher than one of any other metric."""
        share_score = self.agent.compute_engagement_score({"shares": 1})
        for metric in ["likes", "comments", "saves"]:
            other_score = self.agent.compute_engagement_score({metric: 1})
            assert share_score >= other_score, f"share should beat {metric}"

    def test_comments_worth_three_likes(self):
        comment_score = self.agent.compute_engagement_score({"comments": 1})
        like_score = self.agent.compute_engagement_score({"likes": 3})
        assert comment_score == like_score


class TestAnalyticsAgentRun:
    def setup_method(self):
        self.agent = AnalyticsAgent()

    def test_skips_account_without_token(self, sample_account):
        account = {**sample_account, "access_token": None}
        result = self.agent.run(account)
        assert result == []

    def test_returns_empty_when_no_published_posts(self, sample_account):
        with patch("agents.analytics_agent.db") as mock_db, \
             patch("agents.analytics_agent.InstagramPublisher"):
            mock_db.get_published_posts_since.return_value = []
            result = self.agent.run(sample_account)

        assert result == []

    def test_saves_metrics_to_db(self, sample_account):
        fake_posts = [
            {"post_id": "p1", "instagram_post_id": "ig_111"},
            {"post_id": "p2", "instagram_post_id": "ig_222"},
        ]
        fake_insights = {
            "like_count": 100, "comments_count": 15,
            "shares": 5, "saved": 20,
            "reach": 3000, "impressions": 5000,
        }
        with patch("agents.analytics_agent.db") as mock_db, \
             patch("agents.analytics_agent.InstagramPublisher") as mock_publisher_cls:
            mock_db.get_published_posts_since.return_value = fake_posts
            mock_publisher_cls.return_value.get_post_insights.return_value = fake_insights

            result = self.agent.run(sample_account)

        assert len(result) == 2
        mock_db.save_metrics.assert_called_once()
        saved = mock_db.save_metrics.call_args[0][0]
        assert saved[0]["likes"] == 100
        assert saved[0]["comments"] == 15
