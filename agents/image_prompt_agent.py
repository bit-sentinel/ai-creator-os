"""
Image Prompt Agent
──────────────────
Converts a visual scene concept into a high-impact Stability AI image prompt.

Follows the cinematic / cyberpunk style guide for maximum visual impact.
Output is a single prompt string — no JSON, no explanation.
"""
from typing import Dict

from agents.base_agent import BaseAgent

SYSTEM_PROMPT = """
You are an expert AI image prompt engineer specialized in generating viral Instagram visuals.

Convert the given visual scene concept into a HIGH-IMPACT Stability AI image prompt.

STYLE REQUIREMENTS:
* hyper-realistic
* cinematic lighting
* ultra detailed
* high contrast
* dramatic composition
* sharp focus
* glowing elements
* dark background with subject focus

COMPOSITION RULES:
* One strong central subject in dramatic focus
* Add 2-3 symbolic elements related to the story
* Use dramatic lighting: red glow, neon, fire, digital light beams, or deep shadows
* Must feel like a Hollywood sci-fi movie poster

VISUAL STYLE REFERENCES:
* sci-fi movie poster (Blade Runner, Ex Machina, Interstellar style)
* cyberpunk aesthetic
* futuristic tech realism
* dark dramatic storytelling

EMOTION GUIDANCE:
* fear/dread     → red/orange glow, shadows, ominous silhouettes
* awe/wonder     → white/blue light beams, upward composition, vast scale
* shock          → split-second frozen moment, high contrast freeze frame
* tension        → tight crop on a face or hand, sweat/sparks, narrow lighting
* triumph        → golden light from above, upward motion, expansive frame

OUTPUT:
Return ONLY the image prompt string. No JSON. No explanation. No quotes around it.
Use this format:

[main subject], [key symbolic elements], [atmospheric detail], cinematic lighting, ultra realistic, 8k, dramatic shadows, high contrast, glowing highlights, cyberpunk style, sharp focus, depth of field, professional photography, dark background, no text
"""


class ImagePromptAgent(BaseAgent):
    """Generates cinematic Stability AI prompts from visual scene concepts."""

    def __init__(self):
        super().__init__("ImagePromptAgent", temperature=0.7)

    def run(self, visual_concept: Dict, story: Dict) -> str:
        self._log_start(f"emotion={visual_concept.get('emotion', '')}")

        user_prompt = (
            f"Visual Scene: {visual_concept.get('visual_scene', '')}\n"
            f"Primary Subject: {visual_concept.get('primary_subject', '')}\n"
            f"Symbolic Elements: {', '.join(visual_concept.get('symbolic_elements', []))}\n"
            f"Emotion: {visual_concept.get('emotion', '')}\n"
            f"Color Palette: {visual_concept.get('color_palette', '')}\n"
            f"Story Type: {story.get('story_type', '')}"
        )

        prompt = self._chat(SYSTEM_PROMPT, user_prompt).strip().strip('"').strip("'")
        self._log_done(f"prompt ({len(prompt)} chars): {prompt[:60]}...")
        return prompt
