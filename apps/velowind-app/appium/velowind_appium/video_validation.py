from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Iterable
from xml.etree import ElementTree

from PIL import Image


@dataclass(frozen=True)
class VideoBounds:
    x: int
    y: int
    width: int
    height: int


def find_note_detail_video_bounds(page_source: str) -> VideoBounds | None:
    """Find the largest accessible video/player region on a note detail page."""
    if not page_source or not any(marker in page_source for marker in ["写留言", "评论", "post-detail", "message-detail"]):
        return None
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return None
    candidates: list[VideoBounds] = []
    for element in root.iter():
        attributes = element.attrib
        if attributes.get("visible") == "false" or attributes.get("displayed") == "false":
            continue
        searchable = " ".join(
            attributes.get(key, "")
            for key in ["type", "class", "resource-id", "name", "label", "value", "content-desc"]
        ).lower()
        if not any(token in searchable for token in ["video", "player", "avplayer", "surfaceview", "视频"]):
            continue
        bounds = _element_bounds(attributes)
        if bounds is None or bounds.width < 120 or bounds.height < 120:
            continue
        candidates.append(bounds)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.width * item.height)


def _element_bounds(attributes: dict[str, str]) -> VideoBounds | None:
    value = attributes.get("bounds", "")
    if value:
        parts = [part for part in value.replace("[", ",").replace("]", ",").split(",") if part.strip()]
        if len(parts) == 4:
            try:
                left, top, right, bottom = [int(part) for part in parts]
            except ValueError:
                return None
            if right > left and bottom > top:
                return VideoBounds(left, top, right - left, bottom - top)
    try:
        x = int(float(attributes.get("x", "")))
        y = int(float(attributes.get("y", "")))
        width = int(float(attributes.get("width", "")))
        height = int(float(attributes.get("height", "")))
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return VideoBounds(x, y, width, height)


@dataclass(frozen=True)
class VideoComparisonResult:
    is_valid: bool
    source_duration: float
    actual_duration: float
    duration_delta: float
    source_size: tuple[int, int]
    actual_size: tuple[int, int]
    frame_similarity: float
    sampled_frame_count: int
    reason: str


def compare_video_frames(
    source_frames: Iterable[Image.Image],
    actual_frames: Iterable[Image.Image],
    *,
    min_frame_similarity: float = 0.8,
) -> VideoComparisonResult:
    source = [frame.convert("RGB") for frame in source_frames]
    actual = [frame.convert("RGB") for frame in actual_frames]
    if not source or not actual:
        return VideoComparisonResult(
            is_valid=False,
            source_duration=0.0,
            actual_duration=0.0,
            duration_delta=0.0,
            source_size=source[0].size if source else (0, 0),
            actual_size=actual[0].size if actual else (0, 0),
            frame_similarity=0.0,
            sampled_frame_count=0,
            reason="no-video-frames",
        )

    scores = [max(_frame_similarity(source_frame, actual_frame) for source_frame in source) for actual_frame in actual]
    frame_similarity = sum(scores) / len(scores)
    is_valid = frame_similarity >= min_frame_similarity
    return VideoComparisonResult(
        is_valid=is_valid,
        source_duration=0.0,
        actual_duration=0.0,
        duration_delta=0.0,
        source_size=source[0].size,
        actual_size=actual[0].size,
        frame_similarity=round(frame_similarity, 6),
        sampled_frame_count=len(scores),
        reason="ok" if is_valid else "frame-similarity-too-low",
    )


def compare_videos_for_publish(
    source_path: Path,
    actual_path: Path,
    *,
    sample_count: int = 8,
    duration_tolerance: float = 2.0,
    min_frame_similarity: float = 0.8,
) -> VideoComparisonResult:
    source_metadata = _probe_video(source_path)
    actual_metadata = _probe_video(actual_path)
    source_frames = _extract_video_frames(source_path, duration=source_metadata["duration"], sample_count=sample_count)
    actual_frames = _extract_video_frames(actual_path, duration=actual_metadata["duration"], sample_count=sample_count)
    frame_result = compare_video_frames(
        source_frames,
        actual_frames,
        min_frame_similarity=min_frame_similarity,
    )
    duration_delta = abs(source_metadata["duration"] - actual_metadata["duration"])
    resolution_match = (source_metadata["width"], source_metadata["height"]) == (
        actual_metadata["width"],
        actual_metadata["height"],
    )
    is_valid = frame_result.is_valid and duration_delta <= duration_tolerance
    reason = "ok"
    if duration_delta > duration_tolerance:
        reason = "duration-mismatch"
    elif not frame_result.is_valid:
        reason = frame_result.reason
    elif not resolution_match:
        # Server-side transcodes can change dimensions; content similarity is authoritative.
        reason = "ok-transcoded"
    return VideoComparisonResult(
        is_valid=is_valid,
        source_duration=source_metadata["duration"],
        actual_duration=actual_metadata["duration"],
        duration_delta=duration_delta,
        source_size=(source_metadata["width"], source_metadata["height"]),
        actual_size=(actual_metadata["width"], actual_metadata["height"]),
        frame_similarity=frame_result.frame_similarity,
        sampled_frame_count=frame_result.sampled_frame_count,
        reason=reason,
    )


def compare_video_to_frames(
    source_path: Path,
    actual_frames: Iterable[Image.Image],
    *,
    sample_count: int = 8,
    min_frame_similarity: float = 0.8,
) -> VideoComparisonResult:
    """Compare a source video with frames sampled from device screenshots."""
    source_metadata = _probe_video(source_path)
    source_frames = _extract_video_frames(
        source_path,
        duration=source_metadata["duration"],
        sample_count=sample_count,
    )
    frame_result = compare_video_frames(
        source_frames,
        actual_frames,
        min_frame_similarity=min_frame_similarity,
    )
    return VideoComparisonResult(
        is_valid=frame_result.is_valid,
        source_duration=source_metadata["duration"],
        actual_duration=source_metadata["duration"],
        duration_delta=0.0,
        source_size=frame_result.source_size or (source_metadata["width"], source_metadata["height"]),
        actual_size=frame_result.actual_size,
        frame_similarity=frame_result.frame_similarity,
        sampled_frame_count=frame_result.sampled_frame_count,
        reason=frame_result.reason,
    )


def compare_recording_to_source(
    source_path: Path,
    recording_path: Path,
    *,
    crop_bounds: tuple[float, float, float, float] | None = None,
    window_size: tuple[int, int] | None = None,
    sample_count: int = 8,
    min_frame_similarity: float = 0.8,
) -> VideoComparisonResult:
    source_metadata = _probe_video(source_path)
    recording_metadata = _probe_video(recording_path)
    source_frames = _extract_video_frames(source_path, duration=source_metadata["duration"], sample_count=sample_count)
    actual_frames = _extract_video_frames(
        recording_path,
        duration=recording_metadata["duration"],
        sample_count=sample_count,
    )
    if crop_bounds is not None:
        actual_frames = _crop_recording_frames(actual_frames, crop_bounds, window_size)
    frame_result = compare_video_frames(
        source_frames,
        actual_frames,
        min_frame_similarity=min_frame_similarity,
    )
    return VideoComparisonResult(
        is_valid=frame_result.is_valid,
        source_duration=source_metadata["duration"],
        actual_duration=recording_metadata["duration"],
        duration_delta=abs(source_metadata["duration"] - recording_metadata["duration"]),
        source_size=frame_result.source_size,
        actual_size=frame_result.actual_size,
        frame_similarity=frame_result.frame_similarity,
        sampled_frame_count=frame_result.sampled_frame_count,
        reason=frame_result.reason,
    )


def _crop_recording_frames(
    frames: list[Image.Image],
    bounds: tuple[float, float, float, float],
    window_size: tuple[int, int] | None,
) -> list[Image.Image]:
    if not frames:
        return frames
    x, y, width, height = bounds
    window_width, window_height = window_size or (width, height)
    cropped: list[Image.Image] = []
    for frame in frames:
        scale_x = frame.width / window_width if window_width else 1.0
        scale_y = frame.height / window_height if window_height else 1.0
        left = max(0, int(x * scale_x))
        top = max(0, int(y * scale_y))
        right = min(frame.width, int((x + width) * scale_x))
        bottom = min(frame.height, int((y + height) * scale_y))
        if right > left and bottom > top:
            cropped.append(frame.crop((left, top, right, bottom)))
    return cropped


def _frame_similarity(source: Image.Image, actual: Image.Image) -> float:
    size = (max(1, min(source.width, actual.width)), max(1, min(source.height, actual.height)))
    source_resized = source.resize(size)
    actual_resized = actual.resize(size)
    mean_delta = sum(
        abs(source_channel - actual_channel)
        for source_pixel, actual_pixel in zip(source_resized.getdata(), actual_resized.getdata())
        for source_channel, actual_channel in zip(source_pixel, actual_pixel)
    ) / (
        source_resized.width * source_resized.height * 3
    )
    return max(0.0, 1.0 - mean_delta / 255.0)


def _extract_video_frames(path: Path, *, duration: float, sample_count: int) -> list[Image.Image]:
    ffmpeg = _ffmpeg_executable()
    count = max(1, int(sample_count))
    times = [duration * index / max(1, count - 1) for index in range(count)] if duration > 0 else [0.0]
    frames: list[Image.Image] = []
    for timestamp in times:
        result = subprocess.run(
            [
                ffmpeg,
                "-loglevel",
                "error",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "png",
                "pipe:1",
            ],
            check=False,
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0 or not result.stdout:
            continue
        try:
            with Image.open(BytesIO(result.stdout)) as frame:
                frames.append(frame.convert("RGB").copy())
        except Exception:
            continue
    return frames


def _probe_video(path: Path) -> dict[str, float | int]:
    ffmpeg = _ffmpeg_executable()
    result = subprocess.run(
        [ffmpeg, "-i", str(path), "-f", "null", "-"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = result.stderr or result.stdout
    duration_match = re.search(r"Duration:\s+(\d+):(\d+):(\d+(?:\.\d+)?)", output)
    size_match = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", output)
    if duration_match is None or size_match is None:
        raise AssertionError(f"Unable to read video metadata: {path}")
    hours, minutes, seconds = duration_match.groups()
    return {
        "duration": int(hours) * 3600 + int(minutes) * 60 + float(seconds),
        "width": int(size_match.group(1)),
        "height": int(size_match.group(2)),
    }


def _ffmpeg_executable() -> str:
    configured = os.environ.get("VW_FFMPEG_PATH", "").strip()
    if configured and Path(configured).is_file():
        return configured
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as error:
        raise AssertionError("Video validation requires ffmpeg or the imageio-ffmpeg package") from error
