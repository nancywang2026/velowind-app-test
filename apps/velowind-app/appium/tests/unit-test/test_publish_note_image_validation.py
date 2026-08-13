from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw

from velowind_appium.image_validation import (
    ImageBounds,
    compare_publish_note_images,
    crop_image_from_screenshot,
    find_note_detail_image_bounds,
    find_publish_note_preview_image_bounds,
)


def _source_image() -> Image.Image:
    image = Image.new("RGB", (320, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 319, 179), outline="red", width=12)
    draw.rectangle((36, 28, 118, 150), fill="blue")
    draw.ellipse((190, 38, 292, 140), fill="green")
    draw.line((0, 179, 319, 0), fill="black", width=8)
    return image


def test_compare_publish_note_images_accepts_scaled_full_image():
    source = _source_image()
    actual = source.resize((160, 90))

    result = compare_publish_note_images(source, actual)

    assert result.is_valid is True
    assert result.reason == "ok"


def test_compare_publish_note_images_rejects_cropped_image():
    source = _source_image()
    actual = source.crop((64, 0, 256, 180)).resize((160, 90))

    result = compare_publish_note_images(source, actual)

    assert result.is_valid is False
    assert result.reason in {"aspect-ratio-mismatch", "pixel-delta-too-high"}


def test_compare_publish_note_images_accepts_small_aspect_ratio_mismatch():
    source = Image.new("RGB", (1016, 1543), "white")
    actual = Image.new("RGB", (1110, 1480), "white")

    result = compare_publish_note_images(source, actual)

    assert result.is_valid is True
    assert result.reason == "ok"


def test_compare_publish_note_images_accepts_same_content_in_three_four_detail_frame():
    source = Image.new("RGB", (1016, 2004), "white")
    draw = ImageDraw.Draw(source)
    draw.rectangle((20, 20, 996, 1984), outline="red", width=18)
    draw.rectangle((210, 560, 430, 1240), fill="blue")
    draw.ellipse((560, 650, 860, 1120), fill="green")
    draw.line((0, 1002, 1016, 1002), fill="black", width=12)
    detail_crop_height = round(source.width / 0.75)
    crop_top = (source.height - detail_crop_height) // 2
    actual = source.crop((0, crop_top, source.width, crop_top + detail_crop_height)).resize((1110, 1480))

    result = compare_publish_note_images(source, actual)

    assert result.is_valid is True
    assert result.mean_pixel_delta <= 18.0


def test_find_publish_note_preview_image_bounds_accepts_android_preview():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="发布笔记" displayed="true" bounds="[0,0][1080,80]" />
      <android.widget.ImageView resource-id="image" displayed="true" bounds="[42,120][362,300]" />
      <android.widget.TextView text="删除" displayed="true" bounds="[338,96][382,140]" />
    </hierarchy>
    """

    bounds = find_publish_note_preview_image_bounds(page_source)

    assert bounds == ImageBounds(x=42, y=120, width=320, height=180)


def test_crop_image_from_screenshot_scales_xml_bounds_to_png_pixels():
    image = Image.new("RGB", (1080, 2160), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 200, 419, 379), fill="red")
    buffer = BytesIO()
    image.save(buffer, format="PNG")

    cropped = crop_image_from_screenshot(
        buffer.getvalue(),
        ImageBounds(x=50, y=100, width=160, height=90),
        window_size=(540, 1080),
    )

    assert cropped.size == (320, 180)
    assert cropped.getpixel((10, 10)) == (255, 0, 0)


def test_find_note_detail_image_bounds_uses_largest_detail_image():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="写留言" displayed="true" bounds="[0,0][1080,80]" />
      <android.widget.ImageView resource-id="image" displayed="true" bounds="[32,180][1032,742]" />
      <android.widget.ImageView resource-id="image" displayed="true" bounds="[40,820][96,876]" />
    </hierarchy>
    """

    bounds = find_note_detail_image_bounds(page_source)

    assert bounds == ImageBounds(x=32, y=180, width=1000, height=562)
