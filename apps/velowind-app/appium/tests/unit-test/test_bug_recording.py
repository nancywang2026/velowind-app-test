from pathlib import Path

from velowind_appium.bug_recording import (
    BugCapture,
    BugCommand,
    BugRecording,
    SnapshotSummary,
    apply_review_command,
    build_bug_recording_payload,
    generated_step_description,
    parse_bug_command,
    render_bug_report,
    render_taiga_issue,
)


def test_parse_bug_commands():
    assert parse_bug_command("") == BugCommand(kind="capture", text=None)
    assert parse_bug_command("capture 打开搜索页") == BugCommand(kind="capture", text="打开搜索页")
    assert parse_bug_command("actual 页面一直加载中") == BugCommand(kind="actual", text="页面一直加载中")
    assert parse_bug_command("expected 应展示搜索结果") == BugCommand(kind="expected", text="应展示搜索结果")
    assert parse_bug_command("note 第二次复跑通过") == BugCommand(kind="note", text="第二次复跑通过")
    assert parse_bug_command("done") == BugCommand(kind="done", text=None)


def test_generated_step_description_prefers_short_visible_text():
    snapshot = SnapshotSummary(
        screenshot_path="/tmp/step.png",
        xml_path="/tmp/step.xml",
        source_hash="abc",
        visible_ids=["search-input", "submit-button"],
        visible_texts=["搜索", "正在加载真实搜索结果", "第三段忽略"],
        capture_error=None,
    )

    assert generated_step_description(snapshot) == "搜索 / 正在加载真实搜索结果"


def test_generated_step_description_falls_back_to_ids_and_default_text():
    id_snapshot = SnapshotSummary(
        screenshot_path=None,
        xml_path=None,
        source_hash="abc",
        visible_ids=["search-input", "submit-button", "extra"],
        visible_texts=[],
        capture_error=None,
    )
    empty_snapshot = SnapshotSummary(
        screenshot_path=None,
        xml_path=None,
        source_hash="def",
        visible_ids=[],
        visible_texts=[],
        capture_error=None,
    )

    assert generated_step_description(id_snapshot) == "search-input / submit-button"
    assert generated_step_description(empty_snapshot) == "记录当前页面状态"


def test_apply_review_command_keeps_renames_and_deletes_steps():
    recording = BugRecording(
        session_name="search-loading",
        platform="ios",
        title="search-loading",
        environment={"platform": "ios"},
        expected_result="",
        actual_result="",
        notes=[],
        captures=[
            BugCapture(1, "open-search", "打开搜索页", None, "2026-07-24T10:00:00", SnapshotSummary(None, None, "a", [], [], None)),
            BugCapture(2, "loading", "页面加载", None, "2026-07-24T10:01:00", SnapshotSummary(None, None, "b", [], [], None)),
        ],
    )

    assert apply_review_command(recording, "keep") == recording
    assert apply_review_command(recording, "no-op") == recording

    renamed = apply_review_command(recording, "rename 2 搜索结果持续加载不结束")
    assert renamed.captures[1].user_description == "搜索结果持续加载不结束"

    deleted = apply_review_command(renamed, "delete 1")
    assert [capture.index for capture in deleted.captures] == [1]
    assert deleted.captures[0].description == "搜索结果持续加载不结束"


def test_render_bug_report_and_taiga_issue_include_platform_and_evidence():
    recording = BugRecording(
        session_name="search-loading",
        platform="android",
        title="搜索结果持续加载",
        environment={"platform": "android", "app_package": "com.velowind.rider", "udid": "emulator-5554"},
        expected_result="应展示搜索结果或错误态",
        actual_result="页面一直加载中",
        notes=["第二次复跑通过"],
        captures=[
            BugCapture(
                1,
                "open-search",
                "打开搜索页",
                None,
                "2026-07-24T10:00:00",
                SnapshotSummary("/tmp/1.png", "/tmp/1.xml", "a", ["search-input"], ["搜索"], None),
            ),
        ],
    )

    report = render_bug_report(recording, Path("/tmp/recording.json"))
    taiga = render_taiga_issue(recording, Path("/tmp/bug-report.md"))

    assert "Android" in report
    assert "search-loading" in report
    assert "com.velowind.rider" in report
    assert "/tmp/1.png" in report
    assert "/tmp/1.xml" in report
    assert "/tmp/recording.json" in report
    assert "页面一直加载中" in taiga
    assert "/tmp/1.xml" in taiga
    assert "/tmp/bug-report.md" in taiga


def test_build_bug_recording_payload_is_json_ready():
    recording = BugRecording(
        session_name="search-loading",
        platform="ios",
        title="搜索结果持续加载",
        environment={"platform": "ios", "bundle_id": "com.velowind.rider"},
        expected_result="期望",
        actual_result="实际",
        notes=["备注"],
        captures=[
            BugCapture(1, "step-one", "第一步", None, "2026-07-24T10:00:00", SnapshotSummary(None, None, "a", [], [], None)),
        ],
    )

    payload = build_bug_recording_payload(recording, output_dir=Path(".tmp/appium-ios/recordings/search-loading"))

    assert payload["mode"] == "bug"
    assert payload["platform"] == "ios"
    assert payload["environment"]["bundle_id"] == "com.velowind.rider"
    assert payload["output_dir"] == ".tmp/appium-ios/recordings/search-loading"
    assert payload["expected_result"] == "期望"
    assert payload["actual_result"] == "实际"
    assert payload["notes"] == ["备注"]
    assert payload["steps"][0]["snapshot"]["source_hash"] == "a"
