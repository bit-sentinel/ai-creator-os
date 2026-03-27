"""
Hashtag Agent
─────────────
Generates 8-10 high-performing Instagram hashtags for AI news posts.
Mix: 3 broad-reach + 4 mid-tier AI community + 2 story-specific niche tags.
"""
from typing import Dict, List

from agents.base_agent import BaseAgent

SYSTEM_PROMPT = """
You are a social media growth strategist for a viral AI Instagram brand.

Generate exactly 8-10 Instagram hashtags for an AI news post.

MIX STRATEGY:
- 3 broad reach tags (1M+ posts): maximum discoverability
- 4 mid-tier AI community tags (100k-1M posts): targeted AI audience
- 2-3 niche/story-specific tags (<100k posts): less competition, high relevance

ALWAYS include at least 2 from this core AI set:
#artificialintelligence #AI #aitools #futureofwork #chatgpt #openai
#deeplearning #machinelearning #ainews #aifuture #techfuture

STORY TYPE ADDITIONS:
- breakthrough   → #aibreakthrough #techinnovation
- job_disruption → #futureofwork #automation #jobsofthefuture
- controversy    → #aiethics #responsibleai #techethics
- startup        → #aistartup #techstartups #venturecapital
- surveillance   → #aiprivacy #datasurveillance #bigbrother
- capability     → #aitechnology #machinelearning #aicapabilities
- healthcare     → #aiinhealthcare #medtech #healthtech
- military       → #aimiltary #defensetech #autonomousweapons
- future_of_work → #futureofwork #remotework #workautomation
- failure        → #aifailure #techfail #airisks

Return ONLY a JSON array of hashtag strings including the # symbol.
Example: ["#artificialintelligence", "#AI", "#ainews"]
No explanation, no other text.
"""

FALLBACK_HASHTAGS = [
    "#artificialintelligence", "#AI", "#ainews", "#futureofwork",
    "#aitools", "#machinelearning", "#deeplearning", "#openai",
    "#aifuture", "#techinnovation",
]


class HashtagAgent(BaseAgent):
    """Generates optimized 8-10 hashtag sets for AI news posts."""

    def __init__(self):
        super().__init__("HashtagAgent", temperature=0.5)

    def run(self, story: Dict, hook: Dict) -> List[str]:
        self._log_start(f"story_type={story.get('story_type', '')}")

        user_prompt = (
            f"Story Type: {story.get('story_type', '')}\n"
            f"Core Story: {story.get('core_story', '')}\n"
            f"Hook Line 1: {hook.get('line1', '')}"
        )

        try:
            result = self._chat_json(SYSTEM_PROMPT, user_prompt)
            if isinstance(result, list) and len(result) >= 5:
                # Cap at 10
                hashtags = result[:10]
                self._log_done(f"{len(hashtags)} hashtags generated")
                return hashtags
        except Exception as e:
            self._log_error(e, "hashtag_generation")

        self._log_done("using fallback hashtags")
        return FALLBACK_HASHTAGS
