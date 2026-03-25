"""
Design Agent
────────────
Generates carousel slide images using DALL-E 3.
Each slide gets a visually consistent, brand-appropriate image.
"""
import asyncio
import logging
from typing import Dict, List, Optional

from agents.base_agent import BaseAgent
from services.image_generator import ImageGenerator

PROMPT_ENHANCEMENT_SYSTEM = """
You are a visual art director for Instagram carousel posts.

Given a slide's content and role, write an optimized DALL-E 3 image generation prompt.

Style guidelines:
- Modern, clean, minimalist design
- Bold typography areas (leave space for text overlay)
- Consistent colour palette: dark navy or pure white backgrounds
- Professional yet vibrant
- NO faces unless specifically requested
- High contrast for mobile readability

For each slide, tailor the visual to its role:
  hook       → bold, attention-grabbing composition, dramatic lighting
  core_idea  → clean infographic style, simple icons or diagram
  explanation→ step-by-step visual, numbered elements
  insight    → "aha moment" visual metaphor (light bulb, key unlocking door, etc.)
  cta        → warm, inviting, "follow" or "save" implied

Return ONLY the enhanced DALL-E prompt string. Nothing else.
"""

# Brand colour palette applied to all prompts
BRAND_STYLE = (
    "Professional Instagram carousel slide. "
    "Minimalist design. Dark navy blue (#0A0F2C) or pure white background. "
    "Bold sans-serif typography space. "
    "Vibrant accent colour (#4F46E5 indigo). "
    "4K quality, ultra-sharp, no text in image, suitable for business content."
)


class DesignAgent(BaseAgent):
    """Generates images for each carousel slide."""

    def __init__(self):
        super().__init__("DesignAgent", temperature=0.5)
        self.image_generator = ImageGenerator()

    def run(
        self,
        slides: List[Dict],
        niche: str,
        account_username: Optional[str] = None,
    ) -> List[Dict]:
        """
        Generate images for all slides.

        Updates each slide dict in-place with 'image_url'.
        Returns the updated slides list.
        """
        self._log_start(f"niche={niche}, slides={len(slides)}")

        updated_slides = []
        for slide in slides:
            try:
                enhanced_prompt = self._enhance_prompt(slide, niche)
                image_url = self.image_generator.generate(enhanced_prompt)
                slide["image_url"] = image_url
                slide["image_prompt_final"] = enhanced_prompt
                self.logger.info(
                    "Slide %d image generated: %s",
                    slide.get("slide_number", 0),
                    image_url[:60] if image_url else "FAILED",
                )
            except Exception as e:
                self._log_error(e, f"slide {slide.get('slide_number', 0)}")
                slide["image_url"] = ""
                slide["image_error"] = str(e)
            updated_slides.append(slide)

        self._log_done(
            f"Generated {sum(1 for s in updated_slides if s.get('image_url'))} / {len(slides)} images"
        )
        return updated_slides

    # ─── Internal ────────────────────────────────────────────────────────────

    def _enhance_prompt(self, slide: Dict, niche: str) -> str:
        """Use LLM to craft an optimised DALL-E prompt for the slide."""
        base_prompt = slide.get("image_prompt", "")
        role = slide.get("role", "")
        content = slide.get("content", "")
        title = slide.get("title", "")

        user_prompt = (
            f"Niche: {niche}\n"
            f"Slide role: {role}\n"
            f"Slide title: {title}\n"
            f"Slide content: {content}\n"
            f"Base prompt: {base_prompt}"
        )

        enhanced = self._chat(PROMPT_ENHANCEMENT_SYSTEM, user_prompt)
        # Append brand style guidelines
        return f"{enhanced.strip()} {BRAND_STYLE}"
