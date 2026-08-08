from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image, ImageChops, ImageStat


@dataclass(frozen=True)
class ImageBounds:
    x: int
    y: int
    width: int
    height: int

    @property
    def aspect_ratio(self) -> float:
        if self.height <= 0:
            return 0.0
        return self.width / self.height


@dataclass(frozen=True)
class PublishNoteImageComparison:
    is_valid: bool
    source_size: tuple[int, int]
    actual_size: tuple[int, int]
    aspect_ratio_delta: float
    mean_pixel_delta: float
    reason: str


def compare_images_for_publish_note(
    source_path: Path,
    actual_path: Path,
    *,
    max_aspect_ratio_delta: float = 0.1,
    max_mean_pixel_delta: float = 18.0,
) -> PublishNoteImageComparison:
    with Image.open(source_path) as source_image, Image.open(actual_path) as actual_image:
        source = source_image.convert("RGB")
        actual = actual_image.convert("RGB")
        return compare_publish_note_images(
            source,
            actual,
            max_aspect_ratio_delta=max_aspect_ratio_delta,
            max_mean_pixel_delta=max_mean_pixel_delta,
        )


def compare_publish_note_images(
    source: Image.Image,
    actual: Image.Image,
    *,
    max_aspect_ratio_delta: float = 0.1,
    max_mean_pixel_delta: float = 18.0,
) -> PublishNoteImageComparison:
    source = _trim_inner_margin(source.convert("RGB"))
    actual = _trim_inner_margin(actual.convert("RGB"))
    source_ratio = _aspect_ratio(source.size)
    actual_ratio = _aspect_ratio(actual.size)
    ratio_delta = abs(source_ratio - actual_ratio)

    mean_delta = _mean_pixel_delta(source, actual)
    if ratio_delta > max_aspect_ratio_delta:
        mean_delta = min(mean_delta, _best_cover_crop_mean_delta(source, actual))
    is_valid = mean_delta <= max_mean_pixel_delta
    return PublishNoteImageComparison(
        is_valid=is_valid,
        source_size=source.size,
        actual_size=actual.size,
        aspect_ratio_delta=ratio_delta,
        mean_pixel_delta=mean_delta,
        reason="ok" if is_valid else "pixel-delta-too-high",
    )


def crop_image_from_screenshot(
    screenshot_png: bytes,
    bounds: ImageBounds,
    *,
    window_size: tuple[int, int],
) -> Image.Image:
    screenshot = Image.open(BytesIO(screenshot_png)).convert("RGB")
    window_width, window_height = window_size
    scale_x = screenshot.width / window_width if window_width else 1
    scale_y = screenshot.height / window_height if window_height else 1
    left = max(0, int(bounds.x * scale_x))
    upper = max(0, int(bounds.y * scale_y))
    right = min(screenshot.width, int((bounds.x + bounds.width) * scale_x))
    lower = min(screenshot.height, int((bounds.y + bounds.height) * scale_y))
    if right <= left or lower <= upper:
        raise AssertionError(f"Invalid image preview bounds: {bounds}")
    return screenshot.crop((left, upper, right, lower))


def find_publish_note_preview_image_bounds(page_source: str) -> ImageBounds | None:
    if not page_source or "发布笔记" not in page_source:
        return None
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return None

    candidates: list[ImageBounds] = []
    for element in root.iter():
        if element.attrib.get("visible") == "false" or element.attrib.get("displayed") == "false":
            continue
        if not _looks_like_note_preview_image(element):
            continue
        bounds = _element_bounds(element)
        if bounds is None:
            continue
        if bounds.width < 60 or bounds.height < 60:
            continue
        candidates.append(bounds)
    if not candidates:
        return None
    candidates.sort(key=lambda bounds: (bounds.y, bounds.x))
    return candidates[0]


def find_note_detail_image_bounds(page_source: str) -> ImageBounds | None:
    if not page_source or not _looks_like_note_detail_page(page_source):
        return None
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return None

    candidates: list[ImageBounds] = []
    for element in root.iter():
        if element.attrib.get("visible") == "false" or element.attrib.get("displayed") == "false":
            continue
        if not _looks_like_detail_image(element):
            continue
        bounds = _element_bounds(element)
        if bounds is None:
            continue
        if bounds.width < 120 or bounds.height < 120:
            continue
        candidates.append(bounds)
    if not candidates:
        return None
    candidates.sort(key=lambda bounds: (-(bounds.width * bounds.height), bounds.y, bounds.x))
    return candidates[0]


def find_largest_visible_image_bounds(page_source: str) -> ImageBounds | None:
    if not page_source:
        return None
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return None

    candidates: list[ImageBounds] = []
    for element in root.iter():
        if element.attrib.get("visible") == "false" or element.attrib.get("displayed") == "false":
            continue
        if not _looks_like_detail_image(element):
            continue
        bounds = _element_bounds(element)
        if bounds is None or bounds.width < 120 or bounds.height < 120:
            continue
        candidates.append(bounds)
    if not candidates:
        return None
    candidates.sort(key=lambda bounds: (-(bounds.width * bounds.height), bounds.y, bounds.x))
    return candidates[0]


def _looks_like_note_preview_image(element: ElementTree.Element) -> bool:
    tag = element.tag
    resource_id = element.attrib.get("resource-id", "")
    name = element.attrib.get("name", "")
    label = element.attrib.get("label", "")
    if tag == "android.widget.ImageView" and (
        resource_id.endswith(":id/image")
        or resource_id == "image"
        or resource_id.endswith("cropper-image")
        or resource_id == "publish-note-image-picker-cropper-image"
    ):
        return True
    if tag == "XCUIElementTypeImage" and not any(token in name or token in label for token in ["添加", "上传", "关闭"]):
        return True
    return False


def _looks_like_note_detail_page(page_source: str) -> bool:
    return any(
        marker in page_source
        for marker in [
            "post-detail-page",
            "message-detail-page",
            "article-detail-page",
            "post-detail-banner-pager",
            "写留言",
            "评论",
        ]
    )


def _looks_like_detail_image(element: ElementTree.Element) -> bool:
    tag = element.tag
    resource_id = element.attrib.get("resource-id", "")
    name = element.attrib.get("name", "")
    label = element.attrib.get("label", "")
    if tag == "android.widget.ImageView" and (
        resource_id.endswith(":id/image")
        or resource_id == "image"
        or resource_id.endswith("cropper-image")
        or resource_id == "publish-note-image-picker-cropper-image"
    ):
        return True
    if tag == "XCUIElementTypeImage" and not any(token in name or token in label for token in ["头像", "返回", "关闭"]):
        return True
    return False


def _element_bounds(element: ElementTree.Element) -> ImageBounds | None:
    bounds = element.attrib.get("bounds")
    if bounds:
        return _parse_android_bounds(bounds)
    try:
        x = int(float(element.attrib.get("x", "")))
        y = int(float(element.attrib.get("y", "")))
        width = int(float(element.attrib.get("width", "")))
        height = int(float(element.attrib.get("height", "")))
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return ImageBounds(x=x, y=y, width=width, height=height)


def _parse_android_bounds(value: str) -> ImageBounds | None:
    parts = [part for part in value.replace("[", ",").replace("]", ",").split(",") if part.strip()]
    if len(parts) != 4:
        return None
    try:
        left, top, right, bottom = [int(part) for part in parts]
    except ValueError:
        return None
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        return None
    return ImageBounds(x=left, y=top, width=width, height=height)


def _aspect_ratio(size: tuple[int, int]) -> float:
    width, height = size
    return width / height if height else 0.0


def _mean_pixel_delta(source: Image.Image, actual: Image.Image) -> float:
    comparison_size = _comparison_size(actual.size)
    resized_source = source.resize(comparison_size)
    resized_actual = actual.resize(comparison_size)
    diff = ImageChops.difference(resized_source, resized_actual)
    stat = ImageStat.Stat(diff)
    return sum(stat.mean) / len(stat.mean)


def _best_cover_crop_mean_delta(source: Image.Image, actual: Image.Image) -> float:
    actual_ratio = _aspect_ratio(actual.size)
    if actual_ratio <= 0:
        return _mean_pixel_delta(source, actual)

    candidates = list(_cover_crop_candidates(source, actual_ratio))
    return min(_mean_pixel_delta(candidate, actual) for candidate in candidates)


def _cover_crop_candidates(image: Image.Image, target_ratio: float):
    width, height = image.size
    if width <= 0 or height <= 0 or target_ratio <= 0:
        yield image
        return

    current_ratio = width / height
    if current_ratio > target_ratio:
        max_crop_height = height
        max_crop_width = min(width, round(max_crop_height * target_ratio))
    else:
        max_crop_width = width
        max_crop_height = min(height, round(max_crop_width / target_ratio))

    seen: set[tuple[int, int, int, int]] = set()
    for scale in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5):
        crop_width = max(1, round(max_crop_width * scale))
        crop_height = max(1, round(crop_width / target_ratio))
        if crop_width > width or crop_height > height:
            continue
        for anchor_x in (0.0, 0.25, 0.5, 0.75, 1.0):
            left = round((width - crop_width) * anchor_x)
            for anchor_y in (0.0, 0.25, 0.5, 0.75, 1.0):
                top = round((height - crop_height) * anchor_y)
                box = (left, top, left + crop_width, top + crop_height)
                if box in seen:
                    continue
                seen.add(box)
                yield image.crop(box)


def _comparison_size(size: tuple[int, int], max_dimension: int = 320) -> tuple[int, int]:
    width, height = size
    if width <= 0 or height <= 0:
        return (1, 1)
    largest = max(width, height)
    if largest <= max_dimension:
        return size
    scale = max_dimension / largest
    return (max(1, round(width * scale)), max(1, round(height * scale)))


def _trim_inner_margin(image: Image.Image, margin_ratio: float = 0.04) -> Image.Image:
    width, height = image.size
    margin_x = int(width * margin_ratio)
    margin_y = int(height * margin_ratio)
    if margin_x <= 0 or margin_y <= 0:
        return image
    return image.crop((margin_x, margin_y, width - margin_x, height - margin_y))
