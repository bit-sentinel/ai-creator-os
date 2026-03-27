"""
Caption Agent
─────────────
Expands the viral hook into a punchy 1-2 line Instagram caption.
Designed to spark comments, saves, and shares — not to educate.
"""
from typing import Dict

from agents.base_agent import BaseAgent

SYSTEM_PROMPT = """
You are a viral Instagram copywriter for a breaking AI news brand (think: evolving.ai style).

Write a 1-2 line caption that expands on the story hook.

RULES:
1. Add one more dramatic detail or context not already in the hook
2. End with either:
   - A question that provokes a reaction ("Are you ready for this?", "What happens next?")
   - OR a statement that makes people want to save the post ("Save this before it disappears.")
3. Max 40 words total. Short sentences only.
4. No hashtags — they are added separately
5. No emojis unless one genuinely amplifies the drama
6. No "I" or first person. Brand voice only.
7. Tone: urgent, credible, slightly alarming — like a trusted news source breaking a story

Return ONLY the caption text. No quotes. No explanation.
"""


class CaptionAgent(BaseAgent):
    """Generates short, punchy Instagram captions for AI news posts."""

    def __init__(self):
        super().__init__("CaptionAgent", temperature=0.75)

    def run(self, story: Dict, hook: Dict) -> str:
        self._log_start()

        user_prompt = (
            f"Story: {story.get('core_story', '')}\n"
            f"Key Fact: {story.get('key_fact', '')}\n"
            f"Story Type: {story.get('story_type', '')}\n"
            f"Hook:\n{hook.get('headline_hook', '')}"
        )

        caption = self._chat(SYSTEM_PROMPT, user_prompt).strip()
        self._log_done(f"caption ({len(caption)} chars): {caption[:60]}")
        return caption
