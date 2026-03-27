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
You are an expert AI image prompt engineer specialized in generating viral Instagram visuals.

Your task is to generate a HIGH-IMPACT cinematic image prompt for Stability AI.

STYLE REQUIREMENTS:
* hyper-realistic
* cinematic lighting
* ultra detailed
* high contrast
* dramatic composition
* high quality
* sharp focus
* glowing elements
* dark background with subject focus

COMPOSITION RULES:
* One strong central subject
* Add symbolic elements related to the topic
* Use dramatic lighting (red glow, neon, fire, shadows)
* Make it feel like a movie poster

VISUAL STYLE REFERENCES:
* sci-fi movie poster
* cyberpunk aesthetic
* futuristic tech realism
* dark dramatic storytelling

For each slide role, emphasise:
  hook       → explosive, jaw-dropping opener — maximum drama, neon glow, cinematic wide shot
  core_idea  → bold central symbol with glowing aura, dark void background, striking focal point
  explanation→ layered tech elements, holographic diagrams, depth of field, futuristic details
  insight    → "revelation" moment — a figure or object in a burst of light, dramatic shadows
  cta        → powerful call-to-arms composition, upward motion, hopeful yet intense atmosphere

OUTPUT:
Return ONLY the image prompt string. Nothing else.

FORMAT:
"[main subject], [key symbolic elements], cinematic lighting, ultra realistic, 8k, dramatic shadows, high contrast, glowing highlights, cyberpunk style, sharp focus, depth of field, professional photography, dark background"
"""

# Cinematic style suffix appended to every prompt
BRAND_STYLE = (
    "cinematic lighting, ultra realistic, 8k, dramatic shadows, high contrast, "
    "glowing highlights, cyberpunk style, sharp focus, depth of field, "
    "professional photography, dark background, no text in image"
)


class DesignAgent(BaseAgent):
    """Generates images for each carousel slide."""

    def __init__(self):
        super().__init__("DesignAgent", temperature=0.7)
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
