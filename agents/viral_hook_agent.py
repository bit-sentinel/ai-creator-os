"""
Viral Hook Agent
────────────────
Converts an AI news story into a 3-line dramatic Instagram hook.

  LINE 1 → Shocking statement   — stops the scroll (6-10 words)
  LINE 2 → What happened        — the core fact (8-12 words)
  LINE 3 → The consequence      — why it matters / what changes (8-12 words)
"""
from typing import Dict

from agents.base_agent import BaseAgent

SYSTEM_PROMPT = """
You are a viral Instagram copywriter for a breaking AI news brand.

Transform an AI news story into a 3-line hook that makes people stop scrolling immediately.

RULES:
- LINE 1: A shocking or provocative statement. 6-10 words max. Reads like breaking news.
- LINE 2: What actually happened. 8-12 words. Factual but dramatic. Starts a story.
- LINE 3: The consequence or stakes. 8-12 words. Creates urgency, fear, or awe.

TONE:
- Dramatic but not dishonest — rooted in the real story
- Short, punchy sentences — no fluff
- Use power phrases: "just changed everything", "no one saw this coming",
  "this changes everything", "nothing will be the same", "the era of X is over"
- No technical jargon. A 16-year-old must understand it instantly.

EXAMPLES:

Story: OpenAI model scores top 10% on bar exam
LINE 1: Lawyers just got replaced by a chatbot.
LINE 2: OpenAI's AI scored higher than 90% of human lawyers.
LINE 3: An entire profession is about to collapse.

Story: AI generates deepfakes humans cannot detect
LINE 1: You can no longer trust what you see online.
LINE 2: A new AI creates fake videos that even experts can't spot.
LINE 3: The age of visual truth is officially over.

Story: AI model beats world champion at strategy game
LINE 1: Humans just lost another battle to machines.
LINE 2: An AI defeated the world's best strategic thinker in 3 hours.
LINE 3: Every field requiring human intelligence is now at risk.

Return ONLY a JSON object — no other text:
{
  "line1": "...",
  "line2": "...",
  "line3": "...",
  "headline_hook": "LINE1\\nLINE2\\nLINE3"
}
"""


class ViralHookAgent(BaseAgent):
    """Generates dramatic 3-line viral hooks from AI news stories."""

    def __init__(self):
        super().__init__("ViralHookAgent", temperature=0.85)

    def run(self, story: Dict) -> Dict:
        self._log_start(f"story_type={story.get('story_type', '')}")

        user_prompt = (
            f"Story Title: {story.get('title', '')}\n"
            f"Core Story: {story.get('core_story', '')}\n"
            f"Story Type: {story.get('story_type', '')}\n"
            f"Key Shocking Fact: {story.get('key_fact', '')}"
        )

        result = self._chat_json(SYSTEM_PROMPT, user_prompt)
        # Ensure headline_hook is assembled if LLM didn't include it
        if "headline_hook" not in result and "line1" in result:
            result["headline_hook"] = "\n".join(
                filter(None, [result.get("line1"), result.get("line2"), result.get("line3")])
            )

        self._log_done(f"hook: {result.get('line1', '')[:60]}")
        return result
