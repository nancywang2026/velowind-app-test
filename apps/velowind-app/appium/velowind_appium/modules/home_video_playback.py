from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
import time
from xml.etree import ElementTree

from PIL import Image, ImageChops, ImageStat

from velowind_appium.actions import safe_back, swipe_vertical
from velowind_appium.image_validation import crop_image_from_screenshot
from velowind_appium.modules.home_feed import _home_ready_text_present, wait_for_home_feed
from velowind_appium.modules.home_camera_badge import camera_outline_position
from velowind_appium.modules.message_detail import _tap_ios_detail_back_button_from_source
from velowind_appium.reporting import allure, attach_file_if_present, attach_text
from velowind_appium.video_validation import VideoBounds, _element_bounds, find_note_detail_video_bounds


ERRORS = ("post-detail-video-error", "视频暂时不可用", "视频暂时不可播放", "视频或封面处理失败", "视频错误", "播放失败", "详情加载失败", "加载失败")
BLOCKERS = ("post-detail-video-loading", "正在缓冲视频", "post-detail-video-cover", "post-detail-video-paused-overlay")


@dataclass(frozen=True)
class HomeVideo:
    post_id: str
    bounds: VideoBounds


def visible_home_videos(source: str, window: dict, screenshot_png: bytes | None = None) -> list[HomeVideo]:
    """Only cards with a visible camera badge are video candidates."""
    root = ElementTree.fromstring(source)
    videos: dict[str, HomeVideo] = {}
    cards: dict[str, VideoBounds] = {}

    def visit(node, hidden=False):
        hidden = hidden or node.get("visible") == "false" or node.get("displayed") == "false"
        if hidden:
            return
        for key in ("resource-id", "name", "label", "content-desc", "testID"):
            value = node.get(key, "")
            card = re.fullmatch(r"(?:[^\s]+:id/)?post-home-feed-note-card-([^\s]+)", value)
            if card:
                bounds = _element_bounds(node.attrib)
                # Only the corner needs to be visible, not the whole card.
                # Keep it clear of the fixed category header and bottom tabbar.
                if (bounds and bounds.width >= 80 and bounds.height >= 44
                        and bounds.x >= 0 and bounds.x + bounds.width <= window["width"]
                        and bounds.y >= 120 and bounds.y + 44 <= window["height"] - 100):
                    cards[card.group(1)] = bounds
            match = re.fullmatch(r"(?:[^\s]+:id/)?post-home-feed-note-video-badge-([^\s]+)", value)
            if match is None:
                continue
            # Ancestor accessibility labels may aggregate the whole card. Only
            # use an exact ID (allow the Android package resource prefix).
            bounds = _element_bounds(node.attrib)
            if (
                bounds and 0 <= bounds.x and 0 <= bounds.y
                and bounds.x + bounds.width <= window["width"]
                and bounds.y + bounds.height <= window["height"]
            ):
                post_id = match.group(1)
                candidate = HomeVideo(post_id, bounds)
                previous = videos.get(post_id)
                if previous is None or bounds.width * bounds.height < previous.bounds.width * previous.bounds.height:
                    videos[post_id] = candidate
        for child in node:
            visit(child, hidden)

    visit(root)
    if screenshot_png is not None:
        with Image.open(BytesIO(screenshot_png)) as screenshot:
            scale_x, scale_y = screenshot.width / window["width"], screenshot.height / window["height"]
            for post_id, bounds in cards.items():
                if post_id in videos:
                    continue
                left, top = bounds.x + bounds.width - 44, bounds.y + 2
                corner = screenshot.crop((round(left * scale_x), round(top * scale_y), round((left + 42) * scale_x), round((top + 42) * scale_y)))
                position = camera_outline_position(corner)
                if position is not None:
                    x, y = position
                    videos[post_id] = HomeVideo(post_id, VideoBounds(round(left + x * 42) - 8, round(top + y * 42) - 8, 16, 16))
    return sorted(videos.values(), key=lambda video: (video.bounds.y, video.bounds.x))


def _return_to_feed(driver) -> None:
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_ios = str(capabilities.get("platformName", "")).lower() == "ios"
    if not (is_ios and _tap_ios_detail_back_button_from_source(driver)):
        safe_back(driver)
    wait_for_home_feed(driver, timeout=20)


def _visible_source(source: str) -> str:
    root = ElementTree.fromstring(source)

    def visit(node):
        if node.get("visible") == "false" or node.get("displayed") == "false":
            return ""
        return " ".join([*node.attrib.values(), *(visit(child) for child in node)])

    return visit(root)


def _playback_state_source(source: str) -> str:
    """Use concrete visible controls/text, not ancestor accessibility summaries.

    iOS can leave an error message in a visible parent's aggregated label even
    while the error child is hidden or has already been removed.
    """
    states: list[str] = []
    markers = (*ERRORS, *BLOCKERS, "视频错误，请稍后再试。")

    def visit(node):
        if node.get("visible") == "false" or node.get("displayed") == "false":
            return
        for key in ("name", "resource-id", "testID", "content-desc", "label", "text", "value"):
            value = node.get(key, "").split(":id/")[-1].strip()
            if value not in markers:
                continue
            # Explicit state IDs are valid on containers. Human-readable
            # messages must come from a leaf, never a parent's merged label.
            if value.startswith("post-detail-") or len(node) == 0:
                states.append(value)
        for child in node:
            visit(child)

    visit(ElementTree.fromstring(source))
    return " ".join(states)


def _content_frame(frame: Image.Image) -> Image.Image:
    # Exclude controls/progress at the edges; only media motion is evidence.
    width, height = frame.size
    return frame.crop((int(width * .15), int(height * .15), int(width * .85), int(height * .85))).convert("RGB").resize((96, 96))


def _has_content(frame: Image.Image) -> bool:
    histogram = frame.convert("L").histogram()
    return sum(histogram[:12]) / (frame.width * frame.height) < .98 and max(ImageStat.Stat(frame).stddev) > 2


def _frame_changed(previous: Image.Image, current: Image.Image) -> bool:
    delta = ImageChops.difference(previous, current).convert("L")
    # Ignore compression noise and changes affecting only a few pixels.
    return sum(delta.histogram()[16:]) / (delta.width * delta.height) >= .02


def _playback_error_reason(visible: str, marker: str) -> str:
    messages = [text for text in ("视频暂时不可用", "视频错误，请稍后再试。", "视频暂时不可播放", "视频或封面处理失败", "详情加载失败") if text in visible]
    description = "；".join(messages) or "播放器显示错误状态，未能正常播放"
    return f"进入视频详情后播放失败：{description}（检测标识：{marker}）"


def check_video_playback(driver, artifact_dir: Path, *, timeout: float = 30, observe_seconds: float = 8) -> str | None:
    """Return a failure reason, or None after sustained rendered frame changes.

    A static/unsupported player is unverified and fails closed. No retry or
    tapping the player may hide an autoplay failure.
    """
    artifact_dir.mkdir(parents=True, exist_ok=True)
    window = driver.get_window_size()
    deadline = time.monotonic() + timeout
    previous = None
    started = None
    changes = 0
    last_change = None
    samples = 0
    last_reason = "播放器未出现"
    while time.monotonic() < deadline:
        source = driver.page_source
        visible = _playback_state_source(source)
        error = next((marker for marker in ERRORS if marker in visible), None)
        if error:
            png = driver.get_screenshot_as_png()
            after_source = driver.page_source
            confirmed = error in _playback_state_source(after_source)
            prefix = "playback-error" if confirmed else f"transient-state-{time.time_ns()}"
            path = artifact_dir / f"{prefix}.png"
            path.write_bytes(png)
            attach_file_if_present(path, attachment_type=allure.attachment_type.PNG)
            for suffix, xml in (("before", source), ("after", after_source)):
                xml_path = artifact_dir / f"{prefix}-{suffix}.xml"
                xml_path.write_text(xml, encoding="utf-8")
                attach_file_if_present(xml_path, attachment_type=allure.attachment_type.XML)
            if confirmed:
                return _playback_error_reason(visible, error)
            attach_text("未确认的瞬时错误状态", f"{error}：截图后的页面快照已无该可见错误节点，继续检查实际播放。")
            previous, started, changes, last_change = None, None, 0, None
            time.sleep(.2)
            continue
        bounds = find_note_detail_video_bounds(source)
        blocker = next((marker for marker in BLOCKERS if marker in visible), None)
        if bounds is None or blocker:
            previous, started, changes, last_change = None, None, 0, None
            last_reason = blocker or "播放器未出现"
        else:
            png = driver.get_screenshot_as_png()
            frame = _content_frame(crop_image_from_screenshot(png, bounds, window_size=(window["width"], window["height"])))
            # Check after capture too: spinner/cover transitions aren't playback.
            after = _playback_state_source(driver.page_source)
            if any(marker in after for marker in (*ERRORS, *BLOCKERS)) or not _has_content(frame):
                previous, started, changes, last_change = None, None, 0, None
                last_reason = "视频仍在缓冲、显示封面、暂停或黑屏"
            else:
                samples += 1
                path = artifact_dir / f"frame-{samples:02d}.png"
                frame.save(path)
                attach_file_if_present(path, attachment_type=allure.attachment_type.PNG)
                if previous is not None and _frame_changed(previous, frame):
                    changes += 1
                    last_change = time.monotonic()
                previous = frame
                now = time.monotonic()
                if started is None:
                    started = now
                if now - started >= observe_seconds:
                    if changes >= 2 and last_change is not None and now - last_change <= 3:
                        return None
                    return "画面未持续变化，无法确认正常播放（封面或卡帧）"
                last_reason = "连续播放观察时间不足"
        time.sleep(1.3)
    return f"播放验证超时（{timeout:g} 秒）：{last_reason}"


class _RecordedPlaybackFailure(AssertionError):
    """Mark this Allure video step failed before aggregating all four results."""


def verify_four_home_videos(driver, artifact_dir: Path, *, max_swipes: int = 20) -> None:
    seen: set[str] = set()
    results: list[tuple[str, str | None]] = []
    run_dir = artifact_dir / f"home-video-playback-{time.time_ns()}"
    try:
        wait_for_home_feed(driver, timeout=30)
        for page in range(max_swipes + 1):
            # Refresh coordinates after every return; feed virtualization may
            # move cards. Repeated post IDs never count as another sample.
            while True:
                source, window = driver.page_source, driver.get_window_size()
                is_ios = str((getattr(driver, "capabilities", {}) or {}).get("platformName", "")).lower() == "ios"
                screenshot_png = driver.get_screenshot_as_png() if is_ios else None
                videos = visible_home_videos(source, window, screenshot_png)
                video = next((video for video in videos if video.post_id not in seen), None)
                if video is None:
                    break
                seen.add(video.post_id)
                try:
                    with allure.step(f"检查首页视频 {len(results) + 1}/4：{video.post_id}"):
                        if screenshot_png is not None:
                            run_dir.mkdir(parents=True, exist_ok=True)
                            selected = run_dir / f"selected-video-{len(results) + 1}.png"
                            selected.write_bytes(screenshot_png)
                            attach_file_if_present(selected, attachment_type=allure.attachment_type.PNG)
                        bounds = video.bounds
                        driver.execute_script("mobile: tap", {"x": bounds.x + bounds.width // 2, "y": bounds.y + bounds.height // 2})
                        print(f"[home-video] CHECK {len(results) + 1}/4 post_id={video.post_id}", flush=True)
                        reason = check_video_playback(driver, run_dir / f"video-{len(results) + 1}")
                        print(f"[home-video] {'FAIL: ' + reason if reason else 'PASS'} post_id={video.post_id}", flush=True)
                        results.append((video.post_id, reason))
                        if reason is not None:
                            raise _RecordedPlaybackFailure(reason)
                except _RecordedPlaybackFailure:
                    pass
                if sum(reason is not None for _, reason in results) >= 2:
                    details = "；".join(
                        f"第 {index} 个视频 {post_id}：{failure}"
                        for index, (post_id, failure) in enumerate(results, 1) if failure
                    )
                    raise AssertionError(f"视频播放失败：已有 2 个视频不能正常播放，立即终止。{details}")
                if len(results) == 4:
                    failures = [(post_id, reason) for post_id, reason in results if reason]
                    assert not failures, f"视频播放失败：4 个视频中 {len(failures)} 个失败；{failures}"
                    _return_to_feed(driver)
                    return
                # If the card never opened, do not back out of the home tab.
                if not _home_ready_text_present(_visible_source(driver.page_source)):
                    _return_to_feed(driver)
                else:
                    wait_for_home_feed(driver, timeout=20)
            if page < max_swipes:
                swipe_vertical(driver, direction="up")
                time.sleep(.5)
        raise AssertionError(f"视频播放验证未完成：只找到 {len(results)}/4 个不同视频，不能标记通过")
    finally:
        summary = "\n".join(f"{index}. {post_id}: {reason or '正常播放'}" for index, (post_id, reason) in enumerate(results, 1))
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "summary.txt").write_text(summary or "未获得视频播放检查结果", encoding="utf-8")
        attach_text("首页视频播放检查结果", summary or "未获得视频播放检查结果")
