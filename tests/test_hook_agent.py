"""Tests for HookAgent."""
import json
from unittest.mock import MagicMock, patch

import pytest

from agents.hook_agent import HookAgent


MOCK_HOOKS = [
    {"type": "NUMBER_LIST",   "hook": "7 things about AI that nobody tells you", "power_score": 88},
    {"type": "CONTRARIAN",    "hook": "Everyone is wrong about AI productivity",  "power_score": 75},
    {"type": "STORY_OPEN",    "hook": "I spent 30 days using AI and this changed everything", "power_score": 82},
    {"type": "PROVOCATIVE_Q", "hook": "Why are smart people still working manually?", "power_score": 70},
    {"type": "BOLD_STAT",     "hook": "80% of your tasks can be automated today",  "power_score": 91},
]
MOCK_SELECTION = {"selected_hook": "80% of your tasks can be automated today", "reason": "highest emotional trigger"}


class TestHookAgent:
    @pytest.fixture
    def agent(self):
        return HookAgent()

    def test_run_returns_hook_dict(self, agent, sample_strategy_memory):
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.side_effect = [
                json.dumps(MOCK_HOOKS),
                json.dumps(MOCK_SELECTION),
            ]
            result = agent.run(
                topic="AI productivity tools",
                niche="AI & Productivity",
                strategy_memory=sample_strategy_memory,
            )

        assert "hook" in result
        assert "hook_type" in result
        assert "alternatives" in result
        assert result["hook"] == MOCK_SELECTION["selected_hook"]
        assert len(result["alternatives"]) == 4

    def test_run_no_memory(self, agent):
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.side_effect = [
                json.dumps(MOCK_HOOKS),
                json.dumps(MOCK_SELECTION),
            ]
            result = agent.run(topic="Test topic", niche="Marketing")

        assert result["hook"] == MOCK_SELECTION["selected_hook"]

    def test_fallback_on_bad_json(self, agent):
        """Should not raise even when LLM returns invalid JSON."""
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.side_effect = ["NOT VALID JSON AT ALL", json.dumps(MOCK_SELECTION)]
            result = agent.run(topic="fallback topic", niche="Finance")

        assert "hook" in result

    def test_hook_type_extracted(self, agent):
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.side_effect = [
                json.dumps(MOCK_HOOKS),
                json.dumps({"selected_hook": "7 things about AI that nobody tells you", "reason": "curiosity gap"}),
            ]
            result = agent.run(topic="AI", niche="AI & Productivity")

        assert result["hook_type"] == "NUMBER_LIST"
