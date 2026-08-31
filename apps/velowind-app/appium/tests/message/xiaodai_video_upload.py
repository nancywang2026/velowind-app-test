from __future__ import annotations

import os
from pathlib import Path

import yaml

from velowind_appium.modules import load_message_note_draft
from velowind_appium.reporting import attach_text
from velowind_appium.session import ensure_logged_in_for_publish_entry
from velowind_appium.modules import publish_message_note


TESTDATA_PATH = Path(__file__).resolve().parent / "testdata" / "xiaodai_video_notes.yaml"
DEFAULT_DATA_ROOT = Path("/Users/test/Nancy/Testing/testingdata/小黛/视频")
SUCCESS_TOKENS = ["成功", "审核", "待审核", "已发布", "我的笔记", "视频上传中", "视频上传完成", "detail-page"]
SUPPORTED_VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}


def _load_cases() -> list[dict]:
    data = yaml.safe_load(TESTDATA_PATH.read_text(encoding="utf-8")) or {}
    cases = data.get("use_cases", [])
    if not isinstance(cases, list):
        raise AssertionError(f"Invalid 小黛 video testdata format: {TESTDATA_PATH}")
    return [case for case in cases if isinstance(case, dict)]


def xiaodai_video_use_case_ids() -> list[str]:
    return [str(case.get("id", "")).strip() for case in _load_cases() if str(case.get("id", "")).strip()]


def _case_by_id(use_case_id: str) -> dict:
    for case in _load_cases():
        if str(case.get("id", "")).strip() == use_case_id:
            return case
    raise AssertionError(f"Unable to find 小黛 video use case: {use_case_id}")


def xiaodai_source_video_path(use_case_id: str) -> Path:
    case = _case_by_id(use_case_id)
    note = case.get("note") if isinstance(case.get("note"), dict) else {}
    relative_path = str(note.get("source_video", "")).strip()
    if not relative_path:
        raise AssertionError(f"小黛 video use case is missing source_video: {use_case_id}")
    data_root = Path(os.environ.get("VW_XIAODAI_DATA_ROOT", str(DEFAULT_DATA_ROOT))).expanduser()
    source_path = (data_root / relative_path).resolve()

    if source_path.is_file():
        return source_path

    # Existing data folders use the date suffix (for example, 0424), while
    # testdata may use the corresponding album label (小黛0424).
    if not source_path.exists():
        relative = Path(relative_path)
        if len(relative.parts) == 1 and relative.name.startswith("小黛"):
            prefixed_fallback = (data_root / relative.name.removeprefix("小黛")).resolve()
            if prefixed_fallback.is_dir():
                source_path = prefixed_fallback

    if not source_path.is_dir():
        raise AssertionError(f"小黛 source video directory does not exist: {source_path}")

    video_files = sorted(
        (
            path
            for path in source_path.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )
    if not video_files:
        raise AssertionError(f"小黛 source video directory contains no supported video files: {source_path}")
    return video_files[0]


def run_xiaodai_video_upload_case(app_driver, app_config, step, use_case_id: str) -> None:
    draft = load_message_note_draft(use_case_id, testdata_path=TESTDATA_PATH)
    source_video = xiaodai_source_video_path(use_case_id)

    step("prepare-home-session", lambda: ensure_logged_in_for_publish_entry(app_driver, app_config))
    success_signal = step(
        f"publish-xiaodai-video-{use_case_id}",
        lambda: publish_message_note(
            app_driver,
            draft,
            ios_config=app_config,
            timeout=120,
            video_source_path=source_video,
        ),
    )

    attach_text(
        f"xiaodai-video-upload-{use_case_id}",
        "\n".join(
            [
                "1. 已进入首页并完成登录态准备",
                f"2. 文案来源: {draft.caption_image or 'testdata'}",
                f"3. Mac 对应视频: {source_video}",
                f"4. iPhone 视频相册选择序号: {draft.video_index}",
                f"5. 已填写标题: {draft.title}",
                f"6. 已提交并拿到成功信号: {success_signal}",
            ]
        ),
    )

    assert success_signal, f"Expected a success signal after submitting 小黛 video case {use_case_id}"
    assert any(token in success_signal for token in SUCCESS_TOKENS), (
        f"Expected 小黛 video case {use_case_id} to end in a success/review state, got: {success_signal}"
    )
