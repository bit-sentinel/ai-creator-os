"""
Hook Generator Agent
────────────────────
Takes a topic + strategy memory and generates 5 viral hook variations.
Selects the strongest hook using LLM self-evaluation.
"""
import json
import re
from typing import Dict, List, Optional

from agents.base_agent import BaseAgent

GENERATION_SYSTEM_PROMPT = """
You are an elite Instagram copywriter who specialises in creating hooks that stop scrollers.

A great hook must:
1. Create instant curiosity or emotional trigger
2. Be ≤ 12 words
3. Make a bold promise or ask a provocative question
4. Be relevant to the given niche

Hook archetypes (use each for one of the 5 variations):
  - NUMBER_LIST  : "7 things every {role} must know about {topic}"
  - CONTRARIAN   : "Everyone is wrong about {topic}. Here's why:"
  - STORY_OPEN   : "I {did X} for {time} and this changed everything:"
  - PROVOCATIVE_Q: "Why are smart people still struggling with {topic}?"
  - BOLD_STAT    : "{stat/claim} about {topic} that nobody is talking about"

Return ONLY valid JSON — an array of exactly 5 objects:
[{"type": "<archetype>", "hook": "<hook text>", "power_score": <0-100>}]

Do NOT return any text outside the JSON.
"""

SELECTION_SYSTEM_PROMPT = """
You are a viral content strategist. Given a list of hooks and historical performance data,
select the single best hook for maximum engagement.

Consider:
- Past hook patterns that performed well
- The target audience's psychology
- Current trend of the niche

Return ONLY valid JSON:
{"selected_hook": "<hook text>", "reason": "<one sentence>"}
"""


class HookAgent(BaseAgent):
    """Generates and selects the best viral hook for a topic."""

    def __init__(self):
        super().__init__("HookAgent", temperature=0.9)

    def run(
        self,
        topic: str,
        niche: str,
        strategy_memory: Optional[Dict] = None,
    ) -> Dict:
        """
        Generate hooks for a topic and return the best one.

        Returns:
            {"hook": str, "hook_type": str, "alternatives": List[str]}
        """
        self._log_start(f"topic={topic[:60]}")

        hooks = self._generate_hooks(topic, niche)
        best = self._select_best_hook(hooks, strategy_memory)

        result = {
            "hook": best["selected_hook"],
            "hook_type": next(
                (h["type"] for h in hooks if h["hook"] == best["selected_hook"]),
                "unknown",
            ),
            "alternatives": [h["hook"] for h in hooks if h["hook"] != best["selected_hook"]],
        }

        self._log_done(f"hook={result['hook'][:60]}")
        return result

    # ─── Internal ────────────────────────────────────────────────────────────

    def _generate_hooks(self, topic: str, niche: str) -> List[Dict]:
        user_prompt = f"Topic: {topic}\nNiche: {niche}"
        raw = self._chat(GENERATION_SYSTEM_PROMPT, user_prompt)
        try:
            hooks = json.loads(raw)
            if not isinstance(hooks, list):
                raise ValueError("Expected JSON array")
            return hooks
        except Exception as e:
            self.logger.error("Hook generation parse error: %s\nRaw: %s", e, raw[:300])
            # Fallback: return a single generic hook
            return [{"type": "NUMBER_LIST", "hook": f"The truth about {topic} nobody tells you", "power_score": 70}]

    def _select_best_hook(
        self, hooks: List[Dict], strategy_memory: Optional[Dict]
    ) -> Dict:
        memory_context = ""
        if strategy_memory:
            best_hooks = strategy_memory.get("best_hooks", [])
            if best_hooks:
                patterns = [h.get("pattern", "") for h in best_hooks[:5]]
                memory_context = f"\nHistorically best hook patterns: {', '.join(patterns)}"

        hooks_json = json.dumps(hooks, indent=2)
        user_prompt = f"Hooks:\n{hooks_json}{memory_context}"

        raw = self._chat(SELECTION_SYSTEM_PROMPT, user_prompt)
        try:
            return json.loads(raw)
        except Exception:
            # Fallback: pick highest power_score
            best = max(hooks, key=lambda h: h.get("power_score", 0))
            return {"selected_hook": best["hook"], "reason": "highest power score"}
