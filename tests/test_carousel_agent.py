"""Tests for CarouselAgent."""
import json
from unittest.mock import patch

import pytest

from agents.carousel_agent import CarouselAgent


MOCK_CAPTION = "AI is not the future. It's the present.\n\nHere's what you need to start automating today..."
MOCK_HASHTAGS = json.dumps([
    "#AITools", "#ArtificialIntelligence", "#ProductivityHacks",
    "#TechTips", "#FutureOfWork", "#MachineLearning", "#ChatGPT",
    "#AIMarketing", "#DigitalTransformation", "#AutomationTools",
    "#LearnOnInstagram", "#carousel", "#infographic", "#dailytips",
    "#techstartup", "#growthhacking", "#entrepreneurship",
    "#businessgrowth", "#digitalnomad", "#onlinebusiness",
    "#worksmarter", "#sidehustle", "#passiveincome", "#remotework",
    "#mindset", "#success", "#motivation", "#leadership",
    "#innovation", "#startup",
])


class TestCarouselAgent:
    @pytest.fixture
    def agent(self):
        return CarouselAgent()

    @pytest.fixture
    def mock_content(self, sample_slides):
        return {
            "slides": [
                {"slide_number": s["slide_number"], "role": s["role"],
                 "title": s["title"], "content": s["content"],
                 "image_prompt": s["image_prompt"]}
                for s in sample_slides
            ],
            "overall_theme": "AI productivity tools overview",
        }

    def test_run_returns_complete_payload(self, agent, mock_content, sample_strategy_memory):
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.side_effect = [MOCK_CAPTION, MOCK_HASHTAGS]
            result = agent.run(
                content=mock_content,
                topic="AI productivity tools",
                hook="7 AI tools that will change how you work",
                niche="AI & Productivity",
                strategy_memory=sample_strategy_memory,
            )

        assert "slides" in result
        assert "caption" in result
        assert "hashtags" in result
        assert "content_hash" in result
        assert len(result["slides"]) == 5
        assert len(result["hashtags"]) <= 30

    def test_word_limit_enforced(self, agent, sample_strategy_memory):
        long_content = {
            "slides": [
                {
                    "slide_number": i + 1,
                    "role": "hook",
                    "title": "Test",
                    "content": " ".join(["word"] * 40),   # 40 words — over limit
                    "image_prompt": "test",
                }
                for i in range(5)
            ],
            "overall_theme": "test",
        }
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.side_effect = [MOCK_CAPTION, MOCK_HASHTAGS]
            result = agent.run(
                content=long_content,
                topic="test",
                hook="test hook",
                niche="Marketing",
            )

        for slide in result["slides"]:
            assert len(slide["content"].split()) <= 26   # 25 + potential "…"

    def test_content_hash_deterministic(self, agent, mock_content):
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.side_effect = [MOCK_CAPTION, MOCK_HASHTAGS]
            r1 = agent.run(
                content=mock_content, topic="AI tools", hook="the hook",
                niche="AI & Productivity",
            )
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.side_effect = [MOCK_CAPTION, MOCK_HASHTAGS]
            r2 = agent.run(
                content=mock_content, topic="AI tools", hook="the hook",
                niche="AI & Productivity",
            )

        assert r1["content_hash"] == r2["content_hash"]

    def test_content_hash_unique_per_topic(self, agent, mock_content):
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.side_effect = [MOCK_CAPTION, MOCK_HASHTAGS]
            r1 = agent.run(content=mock_content, topic="Topic A", hook="Hook A", niche="test")
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.side_effect = [MOCK_CAPTION, MOCK_HASHTAGS]
            r2 = agent.run(content=mock_content, topic="Topic B", hook="Hook B", niche="test")

        assert r1["content_hash"] != r2["content_hash"]

    def test_pads_to_five_slides(self, agent):
        sparse_content = {
            "slides": [
                {"slide_number": 1, "role": "hook", "title": "Hook", "content": "Test content.", "image_prompt": "hook img"},
            ],
            "overall_theme": "test",
        }
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.side_effect = [MOCK_CAPTION, MOCK_HASHTAGS]
            result = agent.run(content=sparse_content, topic="test", hook="hook", niche="test")

        assert len(result["slides"]) == 5
