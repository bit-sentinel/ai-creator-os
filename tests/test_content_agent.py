"""Tests for ContentAgent."""
import json
from unittest.mock import patch

import pytest

from agents.content_agent import ContentAgent

MOCK_CONTENT_RESPONSE = {
    "slides": [
        {"slide_number": 1, "role": "hook",        "title": "7 AI Tools", "content": "7 AI tools saving hours every week.",     "image_prompt": "bold hook"},
        {"slide_number": 2, "role": "core_idea",   "title": "The Problem", "content": "Most people do manually what AI handles.", "image_prompt": "problem"},
        {"slide_number": 3, "role": "explanation", "title": "The Tools",   "content": "ChatGPT, Zapier, Notion AI lead the pack.", "image_prompt": "tools"},
        {"slide_number": 4, "role": "insight",     "title": "The Secret",  "content": "Prompt quality matters more than the tool.", "image_prompt": "insight"},
        {"slide_number": 5, "role": "cta",         "title": "Try It",      "content": "Save this. Which tool will you start with?", "image_prompt": "cta"},
    ],
    "overall_theme": "AI productivity tools overview",
}


class TestContentAgent:
    @pytest.fixture
    def agent(self):
        return ContentAgent()

    def test_run_returns_five_slides(self, agent, sample_strategy_memory):
        with patch.object(agent, "_chat", return_value=json.dumps(MOCK_CONTENT_RESPONSE)):
            result = agent.run(
                topic="AI productivity tools",
                hook="7 AI tools saving you 10h/week",
                niche="AI & Productivity",
                strategy_memory=sample_strategy_memory,
            )

        assert len(result["slides"]) == 5
        assert "overall_theme" in result

    def test_word_limit_trimmed(self, agent):
        over_limit = {
            "slides": [
                {
                    "slide_number": i + 1,
                    "role": "hook",
                    "title": "Test",
                    "content": " ".join(["word"] * 30),
                    "image_prompt": "img",
                }
                for i in range(5)
            ],
            "overall_theme": "test",
        }
        with patch.object(agent, "_chat", return_value=json.dumps(over_limit)):
            result = agent.run(topic="test", hook="test", niche="test")

        for slide in result["slides"]:
            words = slide["content"].replace("…", "").strip().split()
            assert len(words) <= 25

    def test_fallback_on_invalid_json(self, agent):
        with patch.object(agent, "_chat", return_value="garbage response from LLM"):
            result = agent.run(topic="AI tools", hook="the hook", niche="Marketing")

        assert "slides" in result
        assert len(result["slides"]) == 5

    def test_slide_roles_are_set(self, agent):
        with patch.object(agent, "_chat", return_value=json.dumps(MOCK_CONTENT_RESPONSE)):
            result = agent.run(topic="test", hook="hook", niche="test")

        roles = [s["role"] for s in result["slides"]]
        assert "hook" in roles
        assert "cta" in roles
