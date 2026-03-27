"""
Visual Story Agent
──────────────────
Converts a viral hook + news story into a concrete cinematic visual scene concept.

One scene. One subject. Maximum dramatic impact.
"""
from typing import Dict

from agents.base_agent import BaseAgent

SYSTEM_PROMPT = """
You are a cinematic visual director for a viral AI Instagram brand.

Given an AI news story and its hook, design ONE powerful visual scene that:
1. Captures the EMOTION of the story (fear, awe, shock, wonder, dread, tension)
2. Uses strong, unmistakable symbolism
3. Has ONE clear primary subject in dramatic focus
4. Feels like a frame from a sci-fi movie poster

VISUAL MAPPING GUIDE (use as inspiration):
- AI replacing jobs        → robot sitting at human's desk, office empty, human silhouette walking out
- AI surveillance          → massive glowing digital eye above a city at night, surveillance beams
- AI breakthrough          → humanoid robot ascending toward blinding light, arms outstretched
- AI failure / chaos       → cracked computer screen, sparks flying, red emergency alert lights
- AI making money          → robot hands holding glowing gold coins, dark trading floor with screens
- AI writing / creativity  → robot hand gripping a pen, human shadow watching in disbelief
- AI manipulation / psyops → puppet strings made of glowing code controlling human silhouettes
- AI consciousness / AGI   → robot staring into a mirror and seeing a human reflection staring back
- AI military / warfare    → drone swarm over dark city, explosions below, scanning beams
- AI in healthcare         → robotic arm holding a glowing human heart in a dark operating room
- AI in law                → robot judge at a bench, scales of justice, neon courtroom
- AI deepfakes / deception → two identical faces side-by-side splitting apart like a digital tear
- AI and data/privacy      → human figure dissolving into streams of data and code

COMPOSITION RULES:
- One primary subject, dramatically lit
- Dark or black background
- Glowing, neon, or fire-based lighting
- Cinematic depth and shadows
- No text or readable words in the scene

Return ONLY a JSON object:
{
  "visual_scene": "2-3 sentence description of the exact cinematic scene",
  "primary_subject": "the main subject of the image in a few words",
  "symbolic_elements": ["element1", "element2", "element3"],
  "emotion": "one word from: fear | awe | shock | dread | wonder | tension | triumph | unease",
  "color_palette": "2-3 dominant colors e.g. 'deep crimson, black, electric blue'"
}
"""


class VisualStoryAgent(BaseAgent):
    """Translates a viral hook into a concrete cinematic visual scene concept."""

    def __init__(self):
        super().__init__("VisualStoryAgent", temperature=0.75)

    def run(self, story: Dict, hook: Dict) -> Dict:
        self._log_start(f"story_type={story.get('story_type', '')}")

        user_prompt = (
            f"Story Type: {story.get('story_type', '')}\n"
            f"Core Story: {story.get('core_story', '')}\n"
            f"Hook Line 1: {hook.get('line1', '')}\n"
            f"Hook Line 2: {hook.get('line2', '')}\n"
            f"Hook Line 3: {hook.get('line3', '')}\n"
            f"Key Shocking Fact: {story.get('key_fact', '')}"
        )

        result = self._chat_json(SYSTEM_PROMPT, user_prompt)
        self._log_done(f"scene: {result.get('visual_scene', '')[:70]}")
        return result
