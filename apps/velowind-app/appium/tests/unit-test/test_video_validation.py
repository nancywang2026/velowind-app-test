from pathlib import Path

from PIL import Image

from velowind_appium.video_validation import (
    compare_video_frames,
    compare_video_to_frames,
    compare_videos_for_publish,
    find_note_detail_video_bounds,
)


def test_find_note_detail_video_bounds_prefers_accessible_player_region():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="post-detail-page" visible="true" x="0" y="0" width="402" height="874" />
      <XCUIElementTypeOther name="video-player" label="视频" visible="true" x="0" y="120" width="402" height="402" />
      <XCUIElementTypeImage name="avatar" visible="true" x="10" y="10" width="40" height="40" />
      <XCUIElementTypeStaticText name="评论" visible="true" x="10" y="700" width="80" height="30" />
    </AppiumAUT>
    """

    bounds = find_note_detail_video_bounds(page_source)

    assert bounds is not None
    assert (bounds.x, bounds.y, bounds.width, bounds.height) == (0, 120, 402, 402)


def test_compare_video_frames_accepts_same_content_with_different_frame_sizes():
    source = [Image.new("RGB", (4, 4), "red"), Image.new("RGB", (4, 4), "blue")]
    actual = [Image.new("RGB", (8, 8), "red"), Image.new("RGB", (8, 8), "blue")]

    result = compare_video_frames(source, actual)

    assert result.is_valid is True
    assert result.frame_similarity == 1.0
    assert result.reason == "ok"


def test_compare_video_frames_rejects_different_video_content():
    source = [Image.new("RGB", (4, 4), "red"), Image.new("RGB", (4, 4), "blue")]
    actual = [Image.new("RGB", (8, 8), "green"), Image.new("RGB", (8, 8), "yellow")]

    result = compare_video_frames(source, actual)

    assert result.is_valid is False
    assert result.frame_similarity < 0.9
    assert result.reason == "frame-similarity-too-low"


def test_compare_videos_for_publish_uses_video_specific_comparison(monkeypatch, tmp_path: Path):
    source_path = tmp_path / "source.mp4"
    actual_path = tmp_path / "actual.mp4"
    source_path.write_bytes(b"source")
    actual_path.write_bytes(b"actual")
    calls = []

    monkeypatch.setattr(
        "velowind_appium.video_validation._extract_video_frames",
        lambda path, **kwargs: calls.append(Path(path).name) or [Image.new("RGB", (4, 4), "red")],
    )
    monkeypatch.setattr(
        "velowind_appium.video_validation._probe_video",
        lambda path: {"duration": 1.0, "width": 4, "height": 4},
    )

    result = compare_videos_for_publish(source_path, actual_path)

    assert result.is_valid is True
    assert calls == ["source.mp4", "actual.mp4"]


def test_compare_video_to_frames_uses_source_decoder_and_screenshot_frames(monkeypatch, tmp_path: Path):
    source_path = tmp_path / "source.mp4"
    source_path.write_bytes(b"source")
    monkeypatch.setattr(
        "velowind_appium.video_validation._extract_video_frames",
        lambda path, **kwargs: [Image.new("RGB", (4, 4), "red")],
    )
    monkeypatch.setattr(
        "velowind_appium.video_validation._probe_video",
        lambda path: {"duration": 1.0, "width": 4, "height": 4},
    )

    result = compare_video_to_frames(source_path, [Image.new("RGB", (8, 8), "red")])

    assert result.is_valid is True
    assert result.duration_delta == 0.0
