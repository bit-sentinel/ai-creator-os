"""
Text Overlay Service
─────────────────────
Adds a short attention-grabbing text banner to the bottom of an image.

Style: white bold text on a dark gradient overlay — classic viral news style.
Font:  Impact (bundled with macOS) — the go-to font for meme/news overlays.
"""
import logging
import textwrap
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

IMPACT_FONT = "/System/Library/Fonts/Supplemental/Impact.ttf"
FALLBACK_FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

# Gradient overlay occupies the bottom 30% of the image
OVERLAY_HEIGHT_RATIO = 0.30
TEXT_COLOR = (255, 255, 255)           # white
STROKE_COLOR = (0, 0, 0)              # black stroke for contrast
STROKE_WIDTH = 3


class TextOverlayService:
    """Adds dramatic text to the bottom of an image."""

    def add_text(
        self,
        image_path: str,
        text: str,
        output_path: Optional[str] = None,
        font_size: int = 60,
        username: Optional[str] = None,
    ) -> str:
        """
        Add bold hook text at the bottom center + optional username watermark
        at the bottom-left of the image.

        Args:
            image_path:  Path to source image (local file).
            text:        Short attention-grabbing text (ideally ≤ 8 words).
            output_path: Where to save the result.
            font_size:   Base font size in pixels for the hook text.
            username:    Page handle to show at bottom-left (e.g. '@cognitionlabs.ai').
                         Include the @ or it will be prepended automatically.

        Returns:
            Path to the output image with overlays applied.
        """
        img = Image.open(image_path).convert("RGBA")
        w, h = img.size

        # ── Dark gradient overlay at the bottom ───────────────────────────────
        overlay_h = int(h * OVERLAY_HEIGHT_RATIO)
        overlay = Image.new("RGBA", (w, overlay_h), (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)

        for y in range(overlay_h):
            alpha = int((y / overlay_h) * 200)
            draw_overlay.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))

        img.paste(overlay, (0, h - overlay_h), overlay)

        draw = ImageDraw.Draw(img)

        # ── Hook text — centered, bold, Impact ────────────────────────────────
        font = self._load_font(font_size)
        max_chars = max(10, int(w / (font_size * 0.55)))
        wrapped = "\n".join(textwrap.wrap(text.upper(), width=max_chars))

        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=8)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # Center horizontally inside the gradient zone
        x = (w - text_w) // 2
        y = h - overlay_h + (overlay_h - text_h) // 2

        self._draw_text_with_stroke(draw, x, y, wrapped, font, spacing=8, align="center")

        # ── Username watermark — bottom-left ──────────────────────────────────
        if username:
            handle = username if username.startswith("@") else f"@{username}"
            wm_size = max(22, font_size // 3)
            wm_font = self._load_font(wm_size)
            padding = 18

            wm_bbox = draw.textbbox((0, 0), handle, font=wm_font)
            wm_h = wm_bbox[3] - wm_bbox[1]

            wm_x = padding
            wm_y = h - wm_h - padding

            self._draw_text_with_stroke(
                draw, wm_x, wm_y, handle, wm_font,
                spacing=0, align="left", stroke_width=2,
            )

        # ── Save ──────────────────────────────────────────────────────────────
        result = img.convert("RGB")
        if not output_path:
            p = Path(image_path)
            output_path = str(p.parent / f"{p.stem}_overlay{p.suffix}")

        result.save(output_path, "PNG", quality=95)
        logger.info("Text overlay saved: %s", output_path)
        return output_path

    # ─── Internal ─────────────────────────────────────────────────────────────

    @staticmethod
    def _draw_text_with_stroke(
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        text: str,
        font: ImageFont.FreeTypeFont,
        spacing: int = 8,
        align: str = "center",
        stroke_width: int = STROKE_WIDTH,
    ) -> None:
        """Draw text with a solid black stroke for contrast on any background."""
        for dx in range(-stroke_width, stroke_width + 1):
            for dy in range(-stroke_width, stroke_width + 1):
                if dx != 0 or dy != 0:
                    draw.multiline_text(
                        (x + dx, y + dy), text,
                        font=font, fill=STROKE_COLOR, spacing=spacing, align=align,
                    )
        draw.multiline_text(
            (x, y), text,
            font=font, fill=TEXT_COLOR, spacing=spacing, align=align,
        )

    @staticmethod
    def _load_font(size: int) -> ImageFont.FreeTypeFont:
        for path in (IMPACT_FONT, FALLBACK_FONT):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        logger.warning("No TrueType font found — using default bitmap font")
        return ImageFont.load_default()
