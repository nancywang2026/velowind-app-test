"""Recognize the white camera outline when iOS merges card accessibility.

The mask is the camera glyph from the 2026-09-14 real-device failure capture.
Only the cover's top-right corner is searched, never the photo as a whole.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops


@lru_cache(maxsize=1)
def _camera_masks():
    with Image.open(Path(__file__).resolve().parents[1] / "assets/home-camera-mask.png") as image:
        mask = image.convert("L")
    return tuple(
        mask.resize((round(mask.width * scale), round(mask.height * scale))).point(lambda p: 255 if p >= 128 else 0)
        for scale in (.9, 1, 1.1)
    )


def camera_outline_position(corner: Image.Image) -> tuple[float, float] | None:
    """Return normalized glyph center, requiring both outline and empty interior.

    Input is a 42 x 42 point corner at any screenshot density. White foreground
    alone is insufficient: intersection-over-union also rejects filled shapes,
    text and bright photos that do not have the camera's outline.
    """
    corner = corner.convert("RGB").resize((126, 126))
    binary = Image.new("L", corner.size)
    binary.putdata([255 if min(pixel) >= 210 and max(pixel) - min(pixel) <= 25 else 0 for pixel in corner.getdata()])
    best_score = 0.0
    center = None
    for mask in _camera_masks():
        foreground = mask.histogram()[255]
        # Badge center is about 20 points from the cover's top and right edge.
        # Allow layout rounding and small device/font-scale differences.
        for y in range(24, 65):
            for x in range(24, 65):
                patch = binary.crop((x, y, x + mask.width, y + mask.height))
                count = patch.histogram()[255]
                if count < foreground * .72 or count > foreground / .72:
                    continue
                intersection = ImageChops.multiply(patch, mask).histogram()[255]
                score = intersection / (count + foreground - intersection)
                if score > best_score:
                    best_score = score
                    center = ((x + mask.width / 2) / 126, (y + mask.height / 2) / 126)
    return center if best_score >= .72 else None
