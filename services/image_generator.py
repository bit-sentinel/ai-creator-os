"""
Image Generator Service
────────────────────────
Primary:  Stability AI (Stable Diffusion 3) — REST API, no extra SDK needed.
Fallback: Canva API (if CANVA_API_TOKEN is set).

Claude handles all text generation; this service handles visuals only.
"""
import base64
import logging
import uuid
from pathlib import Path
from typing import Optional

import requests

from config.settings import settings

logger = logging.getLogger(__name__)

IMAGE_CACHE_DIR = Path("./image_cache")

# Stability AI endpoint
STABILITY_BASE = "https://api.stability.ai/v2beta/stable-image/generate"


class ImageGenerator:
    """Generates carousel slide images via Stability AI."""

    def __init__(self):
        IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if not settings.STABILITY_API_KEY:
            logger.warning(
                "STABILITY_API_KEY not set — image generation will fail. "
                "Get a free key at https://platform.stability.ai"
            )

    def generate(self, prompt: str, save_local: bool = True) -> str:
        """
        Generate an image from a prompt.
        Returns a publicly accessible URL (or local file path if no CDN).
        Tries Stability AI → Canva in order.
        """
        if settings.STABILITY_API_KEY:
            try:
                return self._generate_stability(prompt, save_local)
            except Exception as e:
                logger.warning("Stability AI failed: %s. Trying Canva fallback.", e)

        if settings.CANVA_API_TOKEN:
            return self._generate_canva(prompt)

        raise RuntimeError(
            "No image generation provider configured. "
            "Set STABILITY_API_KEY in .env — get a free key at https://platform.stability.ai"
        )

    # ─── Stability AI ─────────────────────────────────────────────────────────

    def _generate_stability(self, prompt: str, save_local: bool) -> str:
        """
        Call Stability AI stable-image/generate endpoint.
        Returns the URL to a locally saved PNG (Stability returns raw bytes).
        """
        model = settings.STABILITY_MODEL
        endpoint = f"{STABILITY_BASE}/sd3" if model.startswith("sd3") else f"{STABILITY_BASE}/core"

        headers = {
            "authorization": f"Bearer {settings.STABILITY_API_KEY}",
            "accept": "image/*",
        }
        data = {
            "prompt": prompt[:10000],
            "output_format": "png",
            "model": model,
        }

        # Parse size (e.g. "1024x1024" → width=1024, height=1024)
        try:
            w, h = settings.STABILITY_IMAGE_SIZE.split("x")
            data["width"] = int(w)
            data["height"] = int(h)
        except Exception:
            pass  # let API use defaults

        resp = requests.post(endpoint, headers=headers, files={"none": ""}, data=data, timeout=60)

        if resp.status_code != 200:
            error_msg = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text[:200]
            raise RuntimeError(f"Stability AI error {resp.status_code}: {error_msg}")

        # Save raw PNG bytes locally
        filename = IMAGE_CACHE_DIR / f"{uuid.uuid4()}.png"
        filename.write_bytes(resp.content)
        logger.info("Stability AI image saved: %s", filename)

        # Return as file:// path — swap for a CDN URL in production
        return filename.resolve().as_uri()

    # ─── Canva (fallback) ─────────────────────────────────────────────────────

    def _generate_canva(self, prompt: str) -> str:
        """Canva Magic Media API fallback."""
        if not settings.CANVA_API_TOKEN:
            raise ValueError("Canva API token not configured")

        headers = {
            "Authorization": f"Bearer {settings.CANVA_API_TOKEN}",
            "Content-Type": "application/json",
        }
        url = "https://api.canva.com/rest/v1/ai/generate-image"
        payload = {"prompt": prompt[:1000], "style": "photo-realistic"}
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp.json().get("image_url", "")
