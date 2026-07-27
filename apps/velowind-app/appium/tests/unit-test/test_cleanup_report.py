import json

from velowind_appium.cleanup import CleanupReport
from velowind_appium.cleanup_config import CleanupConfig
from velowind_appium.cleanup_test_data import build_report_payload, write_report_file


def test_build_report_payload_includes_candidate_details_for_dry_run():
    payload = build_report_payload(
        platform="android",
        dry_run=True,
        cleanup_config=CleanupConfig(
            note_matchers=["测试 -"],
            activity_matchers=["测试 -"],
            session_matchers=["自动化场次"],
            comment_matchers=["自动化评论"],
        ),
        reports=[
            CleanupReport(item_type="note", deleted=[], skipped=["测试 - 长白山"]),
            CleanupReport(item_type="activity", deleted=[], skipped=["测试 - 张家界"]),
        ],
    )

    assert payload["platform"] == "android"
    assert payload["dry_run"] is True
    assert payload["details"] == [
        {
            "item_type": "note",
            "action": "would_delete",
            "text": "测试 - 长白山",
            "matched_by": "测试 -",
        },
        {
            "item_type": "activity",
            "action": "would_delete",
            "text": "测试 - 张家界",
            "matched_by": "测试 -",
        },
    ]


def test_write_report_file_writes_json_under_cleanup_reports(tmp_path):
    report_path = write_report_file(
        artifact_dir=tmp_path,
        payload={"platform": "android", "details": []},
    )

    assert report_path.parent == tmp_path / "cleanup-reports"
    assert report_path.name.startswith("cleanup-report-")
    assert json.loads(report_path.read_text(encoding="utf-8")) == {
        "platform": "android",
        "details": [],
    }
