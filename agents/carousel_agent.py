"""
Carousel Builder Agent
──────────────────────
Takes raw content from ContentAgent and:
1. Validates slide structure and word counts
2. Generates caption and hashtags
3. Produces the final post payload ready for design + publishing
"""
import hashlib
import json
import random
from typing import Dict, List, Optional

from agents.base_agent import BaseAgent

CAPTION_SYSTEM_PROMPT = """
You are an Instagram growth expert who writes captions that drive massive engagement.

Write a caption for an Instagram carousel post.

Rules:
- Open with the hook (already provided)
- 150–300 words total
- Include 3–4 line breaks for readability
- Use emojis sparingly but effectively (max 5)
- End with an engaging question or CTA to comment
- Natural, conversational tone
- Do NOT use hashtags in the caption body

Return ONLY the caption text — no extra commentary.
"""

HASHTAG_SYSTEM_PROMPT = """
You are an Instagram SEO expert.

Generate exactly 30 hashtags for the given topic and niche.

Rules:
- Mix of sizes: 8 niche hashtags (< 500k posts), 12 mid-size (500k-2M), 10 broad (2M+)
- Highly relevant to the content
- No banned hashtags
- Include a mix of topic, audience, and format hashtags (#carousel, #infographic)

Return ONLY valid JSON — an array of 30 hashtag strings (with #).
["#hashtag1", "#hashtag2", ...]

Do NOT output anything else.
"""


class CarouselAgent(BaseAgent):
    """Structures carousel slides and generates caption + hashtags."""

    def __init__(self):
        super().__init__("CarouselAgent", temperature=0.75)

    def run(
        self,
        content: Dict,           # Output from ContentAgent
        topic: str,
        hook: str,
        niche: str,
        account_config: Optional[Dict] = None,
        strategy_memory: Optional[Dict] = None,
    ) -> Dict:
        """
        Build the complete carousel payload.

        Returns a dict with slides, caption, hashtags, and content_hash.
        """
        self._log_start(f"topic={topic[:60]}")

        slides = self._validate_slides(content.get("slides", []))
        caption = self._generate_caption(topic, hook, niche, slides)
        hashtags = self._generate_hashtags(
            topic, niche, account_config, strategy_memory
        )
        content_hash = self._compute_hash(topic, hook)

        payload = {
            "slides": slides,
            "caption": caption,
            "hashtags": hashtags,
            "content_hash": content_hash,
            "overall_theme": content.get("overall_theme", ""),
        }

        self._log_done(f"Carousel ready: {len(slides)} slides, {len(hashtags)} hashtags")
        return payload

    # ─── Slides ──────────────────────────────────────────────────────────────

    def _validate_slides(self, slides: List[Dict]) -> List[Dict]:
        """Ensure exactly 5 slides, enforce word caps, fill missing fields."""
        roles = ["hook", "core_idea", "explanation", "insight", "cta"]
        validated = []
        for i, slide in enumerate(slides[:5]):
            content = slide.get("content", "")
            words = content.split()
            if len(words) > 25:
                content = " ".join(words[:25]) + "…"
            validated.append({
                "slide_number": i + 1,
                "role": slide.get("role", roles[i]),
                "title": slide.get("title", "")[:80],
                "content": content,
                "image_url": slide.get("image_url", ""),      # filled by DesignAgent
                "image_prompt": slide.get("image_prompt", f"Slide {i+1} visual"),
            })
        # Pad if fewer than 5 slides returned
        while len(validated) < 5:
            n = len(validated) + 1
            validated.append({
                "slide_number": n,
                "role": roles[n - 1],
                "title": f"Slide {n}",
                "content": "",
                "image_url": "",
                "image_prompt": f"Minimalist slide {n}",
            })
        return validated

    # ─── Caption ─────────────────────────────────────────────────────────────

    def _generate_caption(
        self, topic: str, hook: str, niche: str, slides: List[Dict]
    ) -> str:
        slide_summary = "\n".join(
            f"Slide {s['slide_number']} ({s['role']}): {s['content']}"
            for s in slides
        )
        user_prompt = (
            f"Topic: {topic}\n"
            f"Niche: {niche}\n"
            f"Hook: {hook}\n\n"
            f"Slide contents:\n{slide_summary}"
        )
        return self._chat(CAPTION_SYSTEM_PROMPT, user_prompt)

    # ─── Hashtags ─────────────────────────────────────────────────────────────

    def _generate_hashtags(
        self,
        topic: str,
        niche: str,
        account_config: Optional[Dict],
        strategy_memory: Optional[Dict],
    ) -> List[str]:
        # Start with account-level hashtag sets if available
        account_tags: List[str] = []
        if account_config and account_config.get("hashtag_sets"):
            pool = account_config["hashtag_sets"]
            account_tags = random.choice(pool) if pool else []

        # LLM-generated topic-specific hashtags
        user_prompt = f"Topic: {topic}\nNiche: {niche}"
        raw = self._chat(HASHTAG_SYSTEM_PROMPT, user_prompt)
        try:
            llm_tags = json.loads(raw)
            if not isinstance(llm_tags, list):
                raise ValueError("Expected array")
        except Exception as e:
            self.logger.error("Hashtag parse error: %s", e)
            llm_tags = [f"#{niche.replace(' ', '')}", "#Instagram", "#LearnOnInstagram"]

        # Merge and deduplicate, injecting account tags
        combined = list(dict.fromkeys(account_tags + llm_tags))

        # Optionally boost best-performing hashtags from memory
        if strategy_memory and strategy_memory.get("best_hashtags"):
            best = [h["tag"] for h in strategy_memory["best_hashtags"][:5]]
            for tag in best:
                if tag not in combined:
                    combined.insert(0, tag)  # Prepend top performers

        return combined[:30]

    # ─── Utilities ───────────────────────────────────────────────────────────

    @staticmethod
    def _compute_hash(topic: str, hook: str) -> str:
        """SHA-256 fingerprint for duplicate detection."""
        raw = f"{topic.lower().strip()}|{hook.lower().strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()
