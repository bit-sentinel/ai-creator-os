"""
Image Generator Service
────────────────────────
Wraps OpenAI DALL-E 3 for carousel slide image generation.
Supports fallback to Canva API if configured.
"""
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

import requests
from openai import OpenAI

from config.settings import settings

logger = logging.getLogger(__name__)

# Local cache directory for downloaded images
IMAGE_CACHE_DIR = Path("./image_cache")


class ImageGenerator:
    """Generates images via DALL-E 3 (primary) or Canva API (fallback)."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def generate(self, prompt: str, save_local: bool = True) -> str:
        """
        Generate an image from a prompt.
        Returns a URL to the generated image.
        If save_local=True, also downloads to ./image_cache/.
        """
        try:
            return self._generate_dalle(prompt, save_local)
        except Exception as e:
            logger.warning("DALL-E failed: %s. Trying fallback.", e)
            if settings.CANVA_API_TOKEN:
                return self._generate_canva(prompt)
            raise

    # ─── DALL-E 3 ─────────────────────────────────────────────────────────────

    def _generate_dalle(self, prompt: str, save_local: bool) -> str:
        # Truncate prompt to DALL-E 4000 char limit
        prompt = prompt[:3900]

        response = self.client.images.generate(
            model=settings.DALLE_MODEL,
            prompt=prompt,
            size=settings.DALLE_IMAGE_SIZE,
            quality=settings.DALLE_IMAGE_QUALITY,
            n=1,
        )
        image_url = response.data[0].url
        logger.info("DALL-E image generated: %s", image_url[:80])

        if save_local:
            self._download_and_cache(image_url)

        return image_url

    def _download_and_cache(self, url: str) -> Optional[Path]:
        """Download DALL-E URL (expires in 1hr) to local cache."""
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            filename = IMAGE_CACHE_DIR / f"{uuid.uuid4()}.png"
            filename.write_bytes(resp.content)
            logger.debug("Image cached at: %s", filename)
            return filename
        except Exception as e:
            logger.warning("Failed to cache image: %s", e)
            return None

    # ─── Canva (fallback) ─────────────────────────────────────────────────────

    def _generate_canva(self, prompt: str) -> str:
        """
        Basic Canva API integration.
        Requires Canva API access (currently in beta).
        """
        if not settings.CANVA_API_TOKEN:
            raise ValueError("Canva API token not configured")

        headers = {
            "Authorization": f"Bearer {settings.CANVA_API_TOKEN}",
            "Content-Type": "application/json",
        }
        # Canva Magic Media API endpoint (adjust when officially released)
        url = "https://api.canva.com/rest/v1/ai/generate-image"
        payload = {
            "prompt": prompt[:1000],
            "style": "photo-realistic",
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data.get("image_url", "")
