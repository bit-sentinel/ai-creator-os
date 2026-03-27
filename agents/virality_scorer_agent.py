"""
Virality Scorer Agent
─────────────────────
Scores each AI news story on four dimensions (0–25 each, total 0–100):

  shock_factor     — How surprising or alarming is this?
  curiosity_gap    — Does it make you desperate to know more?
  visual_potential — How dramatically can it be visualised?
  news_relevance   — Is it timely and broadly relevant?

Only stories scoring ≥ VIRALITY_THRESHOLD advance to content generation.
"""
from typing import Dict, List

from agents.base_agent import BaseAgent

VIRALITY_THRESHOLD = 70

SYSTEM_PROMPT = """
You are a viral content strategist for a high-growth AI Instagram brand.

Score each AI news story on four dimensions (0-25 each). Be strict — most stories score 50-75. Reserve 80+ for genuinely shocking developments.

shock_factor (0-25): How surprising or alarming?
curiosity_gap (0-25): Does it make you desperate to know more?
visual_potential (0-25): How dramatically can it be visualised?
news_relevance (0-25): Is it timely and broadly relevant?

IMPORTANT: Return ONLY a raw JSON array. No explanation, no markdown, no preamble.
Start your response with [ and end with ].

Each element must be exactly:
{"title":"...","core_story":"...","story_type":"...","key_fact":"...","source_url":"...","shock_factor":0,"curiosity_gap":0,"visual_potential":0,"news_relevance":0,"total_score":0,"score_rationale":"..."}
"""


class ViralityScorerAgent(BaseAgent):
    """Scores AI news stories for virality and filters by threshold."""

    def __init__(self):
        super().__init__("ViralityScorerAgent", temperature=0.2)

    BATCH_SIZE = 5   # Keep batches small for reliable JSON output

    def run(
        self, stories: List[Dict], threshold: int = VIRALITY_THRESHOLD
    ) -> List[Dict]:
        self._log_start(f"scoring {len(stories)} stories (threshold={threshold})")
        if not stories:
            return []

        all_scored: List[Dict] = []
        for i in range(0, len(stories), self.BATCH_SIZE):
            batch = stories[i : i + self.BATCH_SIZE]
            scored = self._score_batch(batch)
            all_scored.extend(scored)

        qualified = [s for s in all_scored if s.get("total_score", 0) >= threshold]
        qualified.sort(key=lambda x: x.get("total_score", 0), reverse=True)

        # If scoring failed for all stories (all score=0), fall back to top 3 by raw order
        if not qualified:
            self.logger.warning(
                "No stories passed threshold — scoring may have failed. "
                "Falling back to top 3 stories unscored."
            )
            qualified = [dict(s, total_score=75) for s in stories[:3]]

        self._log_done(
            f"{len(qualified)}/{len(stories)} stories passed threshold {threshold}"
        )
        return qualified

    # ─── Internal ────────────────────────────────────────────────────────────

    def _score_batch(self, stories: List[Dict]) -> List[Dict]:
        stories_text = "\n\n".join(
            f"[{i + 1}]\n"
            f"Title: {stories[i].get('title', '')}\n"
            f"Core story: {stories[i].get('core_story', '')}\n"
            f"Type: {stories[i].get('story_type', '')}\n"
            f"Key fact: {stories[i].get('key_fact', '')}"
            for i in range(len(stories))
        )
        user_prompt = (
            f"Score these {len(stories)} stories. "
            f"Return a JSON array starting with [ and ending with ].\n\n"
            f"{stories_text}"
        )
        try:
            result = self._chat_json(SYSTEM_PROMPT, user_prompt)
            if isinstance(result, list):
                # Merge scores back onto original story dicts (preserve all fields)
                merged = []
                for orig, scored in zip(stories, result):
                    merged.append({**orig, **scored})
                return merged
        except Exception as e:
            self._log_error(e, f"score_batch (size={len(stories)})")

        # Fallback: pass stories through unscored
        return [dict(s, total_score=0) for s in stories]
