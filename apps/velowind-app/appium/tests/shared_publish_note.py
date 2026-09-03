from pathlib import Path

from velowind_appium.cleanup import cleanup_published_note
from velowind_appium.cleanup_config import load_cleanup_config
from velowind_appium.modules import (
    list_message_note_use_case_ids,
    load_message_note_draft,
    publish_message_note,
)
from velowind_appium.reporting import attach_text
from velowind_appium.session import ensure_logged_in_for_publish_entry


TESTDATA_PATH = Path(__file__).resolve().parent / "message" / "testdata" / "publish_notes.yaml"
SUCCESS_TOKENS = ["成功", "审核", "待审核", "已发布", "我的笔记", "视频上传中", "视频上传完成", "detail-page"]


def publish_note_use_case_ids() -> list[str]:
    return [
        use_case_id
        for use_case_id in list_message_note_use_case_ids(testdata_path=TESTDATA_PATH)
        if load_message_note_draft(use_case_id, testdata_path=TESTDATA_PATH).media_type == "image"
    ]


def publish_video_note_use_case_ids() -> list[str]:
    use_case_ids: list[str] = []
    for use_case_id in list_message_note_use_case_ids(testdata_path=TESTDATA_PATH):
        draft = load_message_note_draft(use_case_id, testdata_path=TESTDATA_PATH)
        if draft.media_type == "video" and draft.media_source != "camera":
            use_case_ids.append(use_case_id)
    return use_case_ids


def publish_record_video_note_use_case_ids() -> list[str]:
    use_case_ids: list[str] = []
    for use_case_id in list_message_note_use_case_ids(testdata_path=TESTDATA_PATH):
        draft = load_message_note_draft(use_case_id, testdata_path=TESTDATA_PATH)
        if draft.media_type == "video" and draft.media_source == "camera":
            use_case_ids.append(use_case_id)
    return use_case_ids


def run_publish_note_case(app_driver, app_config, step, use_case_id: str, *, verification_label: str, assertion_label: str) -> None:
    draft = load_message_note_draft(use_case_id, testdata_path=TESTDATA_PATH)

    step("prepare-home-session", lambda: ensure_logged_in_for_publish_entry(app_driver, app_config))
    success_signal = step(
        f"publish-note-for-review-{use_case_id}",
        lambda: publish_message_note(app_driver, draft, ios_config=app_config, timeout=90),
    )

    attach_text(
        verification_label,
        "\n".join(
            [
                "1. 已进入首页并完成登录态准备",
                "2. 已从底部加号/发布入口进入笔记发布流程",
                f"3. 已填写标题: {draft.title}",
                f"4. 已填写话题: {' '.join(draft.topics)}",
                f"5. 已标记地点: {draft.location}",
                f"6. 已设置允许评论: {'是' if draft.allow_comments else '否'}",
                *([f"7. 现场录制视频并读取预览时长: {getattr(app_driver, '_camera_video_actual_seconds', '未知')} 秒"] if draft.media_source == "camera" else []),
                f"{8 if draft.media_source == 'camera' else 7}. 已提交并拿到成功信号: {success_signal}",
            ]
        ),
    )

    assert success_signal, f"Expected a success signal after submitting the {assertion_label} message note for review"
    assert any(token in success_signal for token in SUCCESS_TOKENS), (
        f"Expected the {assertion_label} note publish flow to end in a success/review state, got: {success_signal}"
    )

    cleanup_config = load_cleanup_config()
    if cleanup_config.delete_published_note_after_success:
        step(
            f"cleanup-published-note-{use_case_id}",
            lambda: _cleanup_published_note_after_success(app_driver, app_config, draft.title),
        )


def _cleanup_published_note_after_success(app_driver, app_config, title: str) -> None:
    report = cleanup_published_note(app_driver, title, app_config)
    assert report.deleted in ([], [title]), (
        f"Expected cleanup to delete only the note created by this case, "
        f"got deleted={report.deleted}, skipped={report.skipped}, title={title!r}"
    )
    if not report.deleted:
        attach_text(
            "message-note-cleanup-result",
            f"Published note is not visible in the deletable My Notes list yet; title={title!r}",
        )
