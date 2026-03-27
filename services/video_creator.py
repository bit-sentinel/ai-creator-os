"""
Video Creator Service
──────────────────────
Converts a static image + audio into a vertical MP4 Reel.

Output spec (Instagram Reel):
  - Resolution: 1080 × 1920 (9:16 portrait)
  - Duration:   matches audio length (min 3s, max 90s)
  - Format:     MP4 (H.264 + AAC)
  - FPS:        30

The image is centered on a black 9:16 canvas with a subtle slow-zoom
(Ken Burns effect) for visual life.
"""
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

VIDEO_CACHE_DIR = Path("./video_cache")
REEL_W, REEL_H = 1080, 1920
FPS = 30
ZOOM_FACTOR = 1.05      # 5% zoom over the duration for Ken Burns feel
MIN_DURATION = 5.0      # seconds


class VideoCreator:
    """Creates vertical MP4 Reels from a still image and audio."""

    def __init__(self):
        VIDEO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def create_reel(
        self,
        image_path: str,
        audio_path: str,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Combine a static image and audio into a vertical MP4 Reel.

        Args:
            image_path:  Path to the source image (PNG/JPG).
            audio_path:  Path to the voiceover audio (MP3/WAV).
            output_path: Where to save the MP4. Auto-generated if None.

        Returns:
            Path to the output MP4 file.
        """
        if not output_path:
            output_path = str(VIDEO_CACHE_DIR / f"{uuid.uuid4()}.mp4")

        # Import here so the module loads even if moviepy isn't installed yet
        from moviepy import ImageClip, AudioFileClip, CompositeVideoClip
        from PIL import Image
        import numpy as np

        logger.info("Creating reel: image=%s, audio=%s", image_path, audio_path)

        # ── Load audio to get duration ────────────────────────────────────────
        audio = AudioFileClip(audio_path)
        duration = max(audio.duration + 1.0, MIN_DURATION)  # 1s buffer after speech

        # ── Prepare image on 9:16 canvas ──────────────────────────────────────
        canvas_array = self._fit_image_to_canvas(image_path)

        # ── Build video clip with Ken Burns zoom ──────────────────────────────
        from moviepy import VideoClip

        def make_frame(t):
            """Return a zoomed frame at time t (slow zoom in)."""
            zoom = 1.0 + (ZOOM_FACTOR - 1.0) * (t / duration)
            h, w = canvas_array.shape[:2]
            new_h = int(h / zoom)
            new_w = int(w / zoom)
            y0 = (h - new_h) // 2
            x0 = (w - new_w) // 2
            cropped = canvas_array[y0 : y0 + new_h, x0 : x0 + new_w]
            img = Image.fromarray(cropped).resize((w, h), Image.LANCZOS)
            return np.array(img)

        video = VideoClip(make_frame, duration=duration)
        video = video.with_fps(FPS)
        video = video.with_audio(audio)

        # ── Export ────────────────────────────────────────────────────────────
        video.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=FPS,
            preset="fast",
            logger=None,   # suppress moviepy progress bar in logs
        )

        audio.close()
        video.close()
        logger.info("Reel created: %s (%.1fs)", output_path, duration)
        return output_path

    # ─── Internal ─────────────────────────────────────────────────────────────

    @staticmethod
    def _fit_image_to_canvas(image_path: str):
        """
        Place the source image centered on a 1080×1920 black canvas.
        Scales image to fill width while preserving aspect ratio.
        Returns a numpy array (H, W, 3).
        """
        import numpy as np
        from PIL import Image

        img = Image.open(image_path).convert("RGB")
        img_w, img_h = img.size

        # Scale to fill full width (1080px)
        scale = REEL_W / img_w
        new_w = REEL_W
        new_h = int(img_h * scale)

        img = img.resize((new_w, new_h), Image.LANCZOS)

        # Paste onto black 9:16 canvas, centered vertically
        canvas = Image.new("RGB", (REEL_W, REEL_H), (0, 0, 0))
        y_offset = (REEL_H - new_h) // 2
        canvas.paste(img, (0, max(0, y_offset)))

        return np.array(canvas)
