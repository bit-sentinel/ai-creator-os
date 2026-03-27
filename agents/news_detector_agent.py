"""
AI News Detector Agent
──────────────────────
Filters scraped content for high-impact AI developments only.
Extracts the core story, story type, and the single most shocking fact.
"""
from typing import Dict, List

from agents.base_agent import BaseAgent

SYSTEM_PROMPT = """
You are an AI news editor for a viral Instagram media brand.

Analyze raw scraped content and identify ONLY high-impact AI stories worth posting.

ACCEPT stories about:
- AI breakthroughs or major new model releases
- AI failures, bugs, or unexpected behavior
- AI replacing jobs or automating industries at scale
- Controversial or ethically questionable AI use cases
- Startups using AI in disruptive or surprising ways
- AI surveillance, manipulation, or societal impact
- Shocking AI capabilities people haven't seen before
- Future-of-work transformations driven by AI
- AI being used in military, healthcare, law, or finance in new ways

REJECT:
- Generic tech news not specifically AI-focused
- Minor product updates or UI tweaks
- Academic papers with no real-world impact or application
- Repetitive or already very well-known stories
- Promotional content or marketing announcements

For EACH accepted story return a JSON object with these fields:
{
  "title": "original title from source",
  "core_story": "1-2 sentence summary of what actually happened",
  "story_type": "one of: breakthrough | failure | job_disruption | controversy | startup | surveillance | capability | future_of_work | healthcare | military | finance | legal",
  "key_fact": "the single most shocking or surprising fact in 1 sentence",
  "source_url": "url if available, else empty string"
}

Return a JSON array of accepted stories only.
Return [] if nothing qualifies. No explanations.
"""


class NewsDetectorAgent(BaseAgent):
    """Filters scraped posts for high-impact AI news stories."""

    BATCH_SIZE = 8   # Smaller batches = shorter prompts = cleaner JSON from Claude

    def __init__(self):
        super().__init__("NewsDetectorAgent", temperature=0.2)

    def run(self, raw_posts: List[Dict]) -> List[Dict]:
        self._log_start(f"analyzing {len(raw_posts)} raw posts")
        if not raw_posts:
            return []

        all_stories: List[Dict] = []
        for i in range(0, len(raw_posts), self.BATCH_SIZE):
            batch = raw_posts[i : i + self.BATCH_SIZE]
            stories = self._detect_batch(batch)
            all_stories.extend(stories)

        self._log_done(f"detected {len(all_stories)} AI news stories")
        return all_stories

    # ─── Internal ────────────────────────────────────────────────────────────

    def _detect_batch(self, batch: List[Dict]) -> List[Dict]:
        items_text = "\n\n".join(
            f"[{i + 1}]\n"
            f"Title: {self._safe(p.get('title', ''), 120)}\n"
            f"Text: {self._safe(p.get('text', ''), 200)}\n"
            f"Engagement: likes={p.get('engagement', {}).get('likes', 0)} "
            f"comments={p.get('engagement', {}).get('comments', 0)}"
            for i, p in enumerate(batch)
        )
        user_prompt = (
            f"Analyze these {len(batch)} scraped posts. "
            f"Extract only high-impact AI news stories:\n\n{items_text}"
        )
        try:
            result = self._chat_json(SYSTEM_PROMPT, user_prompt)
            # Re-attach source URLs (kept out of prompt to avoid JSON corruption)
            if isinstance(result, list):
                for item, post in zip(result, batch):
                    if not item.get("source_url"):
                        item["source_url"] = post.get("url", "")
            return result if isinstance(result, list) else []
        except Exception as e:
            self._log_error(e, "detect_batch")
            return []

    @staticmethod
    def _safe(text: str, max_len: int) -> str:
        """Truncate and strip characters that break JSON strings."""
        text = str(text)[:max_len]
        # Remove characters that corrupt JSON: backslashes, raw newlines, stray quotes
        text = text.replace("\\", " ").replace("\n", " ").replace("\r", " ")
        text = text.replace('"', "'").replace("\t", " ")
        return text.strip()
