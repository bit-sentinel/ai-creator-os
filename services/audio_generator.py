"""
Audio Generator Service
────────────────────────
Generates a dramatic TTS voiceover from the post hook using Microsoft Edge TTS
(via the `edge-tts` library — free, no API key required).

Voice selection:
  - Default: en-US-GuyNeural  (deep, authoritative male — suits AI news drama)
  - Alt:     en-US-AriaNeural (clear, confident female)

The voiceover reads the 3-line hook with short pauses between each line
for dramatic effect.
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional

import edge_tts

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "en-US-GuyNeural"
AUDIO_CACHE_DIR = Path("./audio_cache")

# SSML-style pause between hook lines (in ms)
LINE_PAUSE_MS = 600


class AudioGenerator:
    """Generates TTS voiceover audio files for post hooks."""

    def __init__(self, voice: str = DEFAULT_VOICE):
        AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.voice = voice

    def generate_hook_voiceover(
        self,
        line1: str,
        line2: str,
        line3: str,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate a dramatic 3-line hook voiceover.
        Pauses between lines for cinematic effect.

        Returns path to the generated MP3 file.
        """
        if not output_path:
            import uuid
            output_path = str(AUDIO_CACHE_DIR / f"{uuid.uuid4()}.mp3")

        # Build SSML with pauses between lines for dramatic effect
        ssml = self._build_ssml(line1, line2, line3)
        logger.info("Generating voiceover: voice=%s, output=%s", self.voice, output_path)

        asyncio.run(self._synthesize(ssml, output_path))
        logger.info("Voiceover saved: %s", output_path)
        return output_path

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _build_ssml(self, line1: str, line2: str, line3: str) -> str:
        """Build SSML markup with dramatic pauses between lines."""
        pause = f'<break time="{LINE_PAUSE_MS}ms"/>'
        return (
            f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            f'xml:lang="en-US">'
            f'<voice name="{self.voice}">'
            f'<prosody rate="slow" pitch="-5%">'
            f'{line1}{pause}'
            f'{line2}{pause}'
            f'{line3}'
            f'</prosody>'
            f'</voice>'
            f'</speak>'
        )

    @staticmethod
    async def _synthesize(ssml: str, output_path: str) -> None:
        communicate = edge_tts.Communicate(ssml, voice="en-US-GuyNeural")
        await communicate.save(output_path)
