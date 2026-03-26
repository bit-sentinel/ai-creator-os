"""
Content Writer Agent
─────────────────────
Converts a topic + hook into a full 5-slide Instagram carousel script.
Uses strategy memory to bias toward proven content styles.
"""
import json
from typing import Dict, List, Optional

from agents.base_agent import BaseAgent

CONTENT_SYSTEM_PROMPT = """
You are a world-class Instagram educator and content strategist.

Your task is to write the complete content for a 5-slide Instagram carousel.

Rules:
- MAXIMUM 25 words per slide
- Clear, educational tone
- Each slide must flow into the next
- Use simple language (Grade 8 reading level)
- Designed for maximum virality and saves

Carousel structure:
  Slide 1 — HOOK       : The hook (already provided). Add a 1-sentence teaser.
  Slide 2 — CORE IDEA  : Introduce the main concept clearly
  Slide 3 — EXPLANATION: Deep dive with specific examples or data
  Slide 4 — INSIGHT    : A surprising, counterintuitive, or actionable insight
  Slide 5 — CTA        : Call to action — save, share, or follow. End with a question.

Return ONLY valid JSON with this exact structure:
{
  "slides": [
    {
      "slide_number": 1,
      "role": "hook",
      "title": "<bold headline ≤ 8 words>",
      "content": "<body text ≤ 25 words>",
      "image_prompt": "<DALL-E prompt for slide visual>"
    },
    ... (5 slides total)
  ],
  "overall_theme": "<one sentence describing the carousel's core message>"
}

Do NOT output anything outside the JSON.
"""


class ContentAgent(BaseAgent):
    """Writes full carousel content from a topic and hook."""

    def __init__(self):
        super().__init__("ContentAgent", temperature=0.8)

    def run(
        self,
        topic: str,
        hook: str,
        niche: str,
        strategy_memory: Optional[Dict] = None,
        template: Optional[Dict] = None,
    ) -> Dict:
        """
        Generate carousel content.

        Returns dict with "slides" list and "overall_theme" string.
        """
        self._log_start(f"topic={topic[:60]}")

        memory_context = self._build_memory_context(strategy_memory)
        template_context = self._build_template_context(template)

        user_prompt = (
            f"Topic: {topic}\n"
            f"Hook (use this exactly for Slide 1): {hook}\n"
            f"Niche: {niche}\n"
            f"{memory_context}"
            f"{template_context}"
        )

        raw = self._chat(CONTENT_SYSTEM_PROMPT, user_prompt)
        result = self._parse_response(raw, topic, hook)
        result = self._enforce_word_limits(result)

        self._log_done(f"Generated {len(result.get('slides', []))} slides")
        return result

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _build_memory_context(self, memory: Optional[Dict]) -> str:
        if not memory:
            return ""
        lines = []
        if memory.get("best_topics"):
            top_topics = [t["topic"] for t in memory["best_topics"][:3]]
            lines.append(f"High-performing topic themes: {', '.join(top_topics)}")
        if memory.get("best_carousel_format"):
            fmt = memory["best_carousel_format"]
            if fmt.get("best_cta_type"):
                lines.append(f"Best performing CTA type: {fmt['best_cta_type']}")
            if fmt.get("best_slide1_style"):
                lines.append(f"Best slide 1 style: {fmt['best_slide1_style']}")
        return ("\nStrategy context:\n" + "\n".join(lines) + "\n") if lines else ""

    def _build_template_context(self, template: Optional[Dict]) -> str:
        if not template:
            return ""
        return f"\nContent template to follow: {json.dumps(template.get('slide_structure', []))}\n"

    def _parse_response(self, raw: str, topic: str, hook: str) -> Dict:
        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                parts = cleaned.split("```")
                cleaned = parts[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()
            data = json.loads(cleaned)
            if "slides" not in data:
                raise ValueError("Missing 'slides' key")
            return data
        except Exception as e:
            self.logger.error("Content parse error: %s\nRaw: %s", e, raw[:500])
            return self._fallback_content(topic, hook)

    def _enforce_word_limits(self, data: Dict) -> Dict:
        """Trim any slide content exceeding 25 words."""
        for slide in data.get("slides", []):
            content = slide.get("content", "")
            words = content.split()
            if len(words) > 25:
                slide["content"] = " ".join(words[:25]) + "..."
                self.logger.debug("Trimmed slide %d to 25 words", slide.get("slide_number", 0))
        return data

    def _fallback_content(self, topic: str, hook: str) -> Dict:
        """Return minimal valid content if LLM parsing fails."""
        return {
            "slides": [
                {"slide_number": 1, "role": "hook", "title": hook[:50], "content": hook, "image_prompt": f"Modern minimalist slide about {topic}"},
                {"slide_number": 2, "role": "core_idea", "title": "The Big Idea", "content": f"Here's what you need to know about {topic}.", "image_prompt": f"Infographic about {topic}"},
                {"slide_number": 3, "role": "explanation", "title": "How It Works", "content": f"Understanding {topic} can transform your results.", "image_prompt": f"Diagram explaining {topic}"},
                {"slide_number": 4, "role": "insight", "title": "The Key Insight", "content": f"Most people miss the most important part of {topic}.", "image_prompt": f"Light bulb moment, {topic}"},
                {"slide_number": 5, "role": "cta", "title": "Your Next Step", "content": "Save this post. What's your biggest challenge with this?", "image_prompt": "Call to action, follow for more tips"},
            ],
            "overall_theme": f"Educational breakdown of {topic}",
        }
